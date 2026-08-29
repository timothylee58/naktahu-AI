"""router_node — fast intent/language/domain classifier using ILMU chat model."""
from __future__ import annotations

import asyncio
import re

import structlog
import weave

from app.models.state import AgentState
from app.orchestration.circuit_breaker import CircuitOpenError, ilmu_breaker
from app.services import cache as cache_svc
from app.services.llm_client import ILMU_CHAT_MODEL, extract_json_object, ilmu_client

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a query classifier for a Malaysian knowledge base. "
    "Return JSON with: language (bm, en, or zh for Mandarin Chinese), domain (one of: government, education, "
    "legal, finance, healthcare, epf, tax, business, immigration, culture, parliament, property, welfare), intent (string summary max 10 words), "
    "is_live_status_query (boolean), place_name (string or null), "
    "is_structured_parliament_query (boolean), parliament_bill_number (string or null), parliament_mp_query (string or null). "
    "Use 'parliament' for questions about Members of Parliament, constituencies, voting records, bills, or Hansard. "
    "Set is_structured_parliament_query=true ONLY when the query asks for a specific, "
    "lookupable fact: how a named bill's vote broke down (set parliament_bill_number to the "
    "bill number/name as written, e.g. 'RUU 355' or 'D.R. 15/2026'), or who a specific MP or "
    "constituency is (set parliament_mp_query to the MP's name or constituency name as written, "
    "e.g. 'Bangi' or 'YB Anwar Ibrahim'). Set it to false, even for domain='parliament', for "
    "general questions about parliamentary debates, Hansard content, or what was discussed "
    "(e.g. 'what did parliament debate about tax reform'), since those need document search, "
    "not a structured lookup. Never set both parliament_bill_number and parliament_mp_query at "
    "once; pick whichever the query is actually asking for. "
    "Use 'property' for land titles, strata management, tenancy, or e-Tanah matters. "
    "Use 'welfare' for cost-of-living assistance, social welfare aid, or government relief schemes "
    "(electricity/utility rebates, food aid, housing assistance, income-support initiatives) — "
    "distinct from 'finance' (personal financial products/advice) and 'government' (general civic services). "
    "Set is_live_status_query=true ONLY for questions asking whether a specific named "
    "restaurant/warung/kopitiam/food stall is currently busy, packed, crowded, or has a "
    "queue right now (e.g. 'Is Pelita packed right now?', 'Ada line tak kat Village Park sekarang?'). "
    "This is a distinct category from general knowledge questions about government/business/etc — "
    "it is about live real-time crowd status at one specific named place, not a rule or fact lookup. "
    "When true, set place_name to the place's name exactly as written in the query (no city/address). "
    "Detect language from the query text itself, not from any metadata."
)

# scam_check is deliberately EXCLUDED here, unlike ingest_feed.py's/
# check_domain_coverage.py's/evals' copies of this list. Those cover content/
# schema validity (document_chunks.domain, eval-dataset tagging); this set
# is specifically "domains the general chat classifier may route into". A
# general chat query must never be classified into scam_check — that path
# skips check_node.py's deterministic official-domain check entirely, and
# the general RAG synthesiser must never be the thing that decides whether
# a link is safe. scam_check is reachable only via its own dedicated
# endpoint (POST /api/v1/agents/scam-check-agent/start). Confirmed
# high-severity finding from an automated review; test_router_node.py
# asserts scam_check never appears in _SYSTEM_PROMPT as the guard for this.
_VALID_DOMAINS = {"government", "education", "legal", "finance", "healthcare", "epf", "tax", "business", "immigration", "culture", "parliament", "property", "welfare"}
# Map common LLM outputs to stored domain values
_DOMAIN_ALIASES = {
    "health": "healthcare",
    "epf": "epf",
    "pension": "epf",
    "kwsp": "epf",
    "eis": "epf",
    "socso": "epf",
    "perkeso": "epf",
    "tax": "tax",
    "cukai": "tax",
    "tanah": "property",
    "hartanah": "property",
    "e-tanah": "property",
    "strata": "property",
    "sewa": "property",
}

# Unicode ranges that unambiguously identify script
_CJK_RE = re.compile(r'[一-鿿㐀-䶿豈-﫿]')


def _script_detect(query: str) -> str | None:
    """Return 'zh' if the query contains CJK characters, else None."""
    return "zh" if _CJK_RE.search(query) else None


@weave.op()
async def router_node(state: AgentState) -> dict:
    """Classify query intent, language, and domain."""
    query = state.get("query", "")

    preset_domain = state.get("domain")
    if isinstance(preset_domain, str):
        preset_domain = preset_domain.strip().lower()
        preset_domain = _DOMAIN_ALIASES.get(preset_domain, preset_domain)

    # Deterministic script check before calling the LLM — CJK is unambiguous
    script_lang = _script_detect(query)

    # Speculative query embedding — started here so it runs concurrently
    # with this node's own classification call below, instead of rag_node
    # only starting it after router_node has fully finished. Only fired
    # when cache.has_query_been_seen() is False, which guarantees the real,
    # domain-scoped cache lookup in rag_node will also miss (the "seen"
    # marker is only ever set alongside a real cache write — see its
    # docstring) — so this embedding is never wasted work on what would
    # have been a cache hit. Imported lazily (not at module level) so
    # nothing here depends on rag_node's own import graph beyond this one
    # function call, matching guard_node's existing lazy-import-for-
    # patchability convention.
    speculative_embedding_task = None
    if query and not await cache_svc.has_query_been_seen(query):
        from app.agents.rag_node import _embed

        speculative_embedding_task = asyncio.create_task(_embed(query))

    try:
        # Routed through ilmu_breaker so a degraded/hanging ILMU provider
        # fails fast (CircuitOpenError, same except-Exception fallback
        # below) instead of every request in the classification hot path
        # queuing up behind individual timeouts. Was previously called
        # directly — the breaker existed but wrapped nothing anywhere in
        # the codebase (found during a full-codebase complexity trace).
        resp = await ilmu_breaker.call(
            ilmu_client.chat.completions.create,
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=128,
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        # Extract JSON even when the model wraps it in markdown fences or
        # appends trailing commentary (extract_json_object handles both —
        # see its docstring for why a greedy regex here silently corrupts
        # correct classifications).
        parsed = extract_json_object(raw)
    except CircuitOpenError:
        log.warning("router_node_circuit_open", provider="ilmu", query_len=len(query))
        parsed = {}
    except Exception as exc:
        log.warning("router_node_error", error=str(exc), query_len=len(query))
        parsed = {}

    language = parsed.get("language", "en")
    if isinstance(language, str):
        language = language.strip().lower()
    if language not in {"bm", "en", "zh"}:
        language = "en"

    # Script detection overrides LLM when CJK characters are present —
    # ILMU may misclassify Mandarin queries as 'bm' since it's Malaysia-tuned
    if script_lang:
        language = script_lang

    # Unset (not "government") when the classifier didn't return a usable
    # domain — "government" is a legitimate classification outcome for a
    # query the LLM actually placed there, but it must never be a stand-in
    # for "couldn't classify". hybrid_search treats domain=None as
    # search-everything; defaulting to a specific domain here risks
    # silently confining retrieval to whichever domain is currently
    # emptiest (has happened — CLAUDE.md Trap #6).
    domain = parsed.get("domain")
    if isinstance(domain, str):
        domain = domain.strip().lower()
        domain = _DOMAIN_ALIASES.get(domain, domain)
    else:
        # A malformed LLM response could put a list/dict here — unhashable,
        # so _DOMAIN_ALIASES.get(domain, domain) would raise TypeError.
        domain = None
    if preset_domain in _VALID_DOMAINS:
        domain = preset_domain
    elif domain not in _VALID_DOMAINS:
        domain = None

    intent = parsed.get("intent", "")
    if not isinstance(intent, str):
        intent = ""

    is_live_status_query = bool(parsed.get("is_live_status_query") is True)
    place_name = parsed.get("place_name")
    if not isinstance(place_name, str) or not place_name.strip():
        place_name = None
        # A malformed classification (flag true, no usable name) can't be
        # routed anywhere useful — fall back to the normal RAG path rather
        # than sending warung_watch_node a query it can't search on.
        is_live_status_query = False

    is_structured_parliament_query = bool(parsed.get("is_structured_parliament_query") is True)
    parliament_bill_number = parsed.get("parliament_bill_number")
    if not isinstance(parliament_bill_number, str) or not parliament_bill_number.strip():
        parliament_bill_number = None
    parliament_mp_query = parsed.get("parliament_mp_query")
    if not isinstance(parliament_mp_query, str) or not parliament_mp_query.strip():
        parliament_mp_query = None
    if not parliament_bill_number and not parliament_mp_query:
        # Same "flag true, no usable entity" guard as is_live_status_query
        # above — parliament_query_node has nothing to look up otherwise.
        is_structured_parliament_query = False

    log.info(
        "router_classified",
        language=language,
        domain=domain,
        intent=intent,
        is_live_status_query=is_live_status_query,
        place_name=place_name,
        is_structured_parliament_query=is_structured_parliament_query,
        parliament_bill_number=parliament_bill_number,
        parliament_mp_query=parliament_mp_query,
    )
    # Handed to rag_node via state; if this query instead gets blocked by
    # guard_node or routed to warung_watch_node (neither of which reads
    # this field — see graph.py), the task simply finishes in the
    # background and is garbage-collected. A harmless, rare exception to
    # "never wasted" (those paths skip rag_node entirely by design), not
    # worth adding cancellation plumbing for.
    return {
        "language": language,
        "domain": domain,
        "intent": intent,
        "is_live_status_query": is_live_status_query,
        "place_name": place_name,
        "is_structured_parliament_query": is_structured_parliament_query,
        "parliament_bill_number": parliament_bill_number,
        "parliament_mp_query": parliament_mp_query,
        "_speculative_embedding_task": speculative_embedding_task,
    }
