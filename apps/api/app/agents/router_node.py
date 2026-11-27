"""router_node — fast intent/language/domain classifier using ILMU chat model."""
from __future__ import annotations

import asyncio
import os
import re
import time

import openai
import structlog
import weave

from app.models.state import AgentState
from app.orchestration.circuit_breaker import CircuitOpenError, anthropic_breaker, ilmu_breaker
from app.services import cache as cache_svc
from app.services.language_detect import detect_latin_language
from app.services.llm_client import (
    FALLBACK_MODEL,
    ILMU_CHAT_MODEL,
    anthropic_client,
    extract_json_object,
    ilmu_client,
)

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
    "e.g. 'Bangi' or 'YB Anwar Ibrahim'). A question about the asker's OWN MP or seat "
    "('who is my MP', 'Ahli Parlimen kawasan saya', '我的国会议员') is also a structured lookup: "
    "set parliament_mp_query to the 5-digit postcode if the query gives one, otherwise to the "
    "phrase as written (e.g. 'my constituency'). Set it to false, even for domain='parliament', for "
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

_ROUTER_TOOL_NAME = "classify_query"
_CLASSIFY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "language": {"type": "string", "enum": ["bm", "en", "zh"]},
        "domain": {"type": ["string", "null"], "enum": [*sorted(_VALID_DOMAINS), None]},
        "intent": {"type": "string"},
        "is_live_status_query": {"type": "boolean"},
        "place_name": {"type": ["string", "null"]},
        "is_structured_parliament_query": {"type": "boolean"},
        "parliament_bill_number": {"type": ["string", "null"]},
        "parliament_mp_query": {"type": ["string", "null"]},
    },
    "required": [
        "language",
        "domain",
        "intent",
        "is_live_status_query",
        "place_name",
        "is_structured_parliament_query",
        "parliament_bill_number",
        "parliament_mp_query",
    ],
    "additionalProperties": False,
}
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


_FIRST_PASS_MAX_TOKENS = 128
_RETRY_MAX_TOKENS = 384


async def _classify_plain(query: str) -> dict:
    """Prompt-and-parse classification: the original path and the fallback for both structured modes."""
    parsed: dict = {}
    for max_tokens in (_FIRST_PASS_MAX_TOKENS, _RETRY_MAX_TOKENS):
        resp = await ilmu_breaker.call(
            ilmu_client.chat.completions.create,
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=max_tokens,
            temperature=0,
        )
        choice = resp.choices[0]
        raw = choice.message.content or ""
        parsed = extract_json_object(raw)
        if parsed:
            return parsed
        # A 200 with unparseable content previously collapsed silently to domain=None
        # (unscoped search); the finish_reason tells truncation apart from non-JSON output.
        log.warning(
            "router_parse_failed",
            finish_reason=getattr(choice, "finish_reason", None),
            content_len=len(raw),
            preview=raw[:120],
            max_tokens=max_tokens,
        )
    return parsed


def _structured_mode() -> str:
    """Read per call (not at import) so Railway env changes and tests take effect without a reload.

    off          prompt-and-parse only (default; nothing is sent that ILMU hasn't already accepted)
    ilmu_schema  ILMU response_format=json_schema; run scripts/probe_ilmu_capabilities.py first
    claude_tool  Anthropic forced tool_use; routes classification through Anthropic, an
                 architecture decision (CLAUDE.md provider order) made explicitly by the owner
    """
    mode = os.environ.get("ROUTER_STRUCTURED_MODE", "off").strip().lower()
    return mode if mode in {"ilmu_schema", "claude_tool"} else "off"


def router_claude_model() -> str:
    """Single source for the claude_tool model so the capability probe tests what production calls."""
    return os.environ.get("ROUTER_CLAUDE_MODEL", FALLBACK_MODEL)


# A deterministic 4xx on response_format means ILMU does not take the schema; retrying it on
# every query would add a wasted round trip per request. Skip the structured call for a while.
_SCHEMA_REJECTED_COOLDOWN_S = 300.0
_schema_rejected_until = 0.0
_REJECTION_STATUSES = {400, 404, 422}
_CLAUDE_TIMEOUT_S = 8.0


async def _classify_ilmu_schema(query: str) -> dict:
    if time.monotonic() < _schema_rejected_until:
        return {}

    async def _create() -> object | None:
        global _schema_rejected_until
        # A schema rejection is a property of the request, not an ILMU outage: converting it to a
        # return value keeps it off ilmu_breaker, which the plain path and guard_node share.
        try:
            # Single pass at the larger budget: the schema bounds the output, and a 128-token
            # truncation would give invalid JSON for no benefit.
            return await ilmu_client.chat.completions.create(
                model=ILMU_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                max_tokens=_RETRY_MAX_TOKENS,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "router_classification", "strict": True, "schema": _CLASSIFY_SCHEMA},
                },
            )
        except openai.APIStatusError as exc:
            if exc.status_code not in _REJECTION_STATUSES:
                raise
            _schema_rejected_until = time.monotonic() + _SCHEMA_REJECTED_COOLDOWN_S
            log.warning("router_schema_rejected", status=exc.status_code, cooldown_s=_SCHEMA_REJECTED_COOLDOWN_S)
            return None

    resp = await ilmu_breaker.call(_create)
    if resp is None:
        return {}
    return extract_json_object(resp.choices[0].message.content or "")


async def _classify_claude_tool(query: str) -> dict:
    resp = await anthropic_breaker.call(
        anthropic_client.messages.create,
        model=router_claude_model(),
        max_tokens=_RETRY_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        tools=[
            {
                "name": _ROUTER_TOOL_NAME,
                "description": "Record the classification of the user's query.",
                "input_schema": _CLASSIFY_SCHEMA,
            }
        ],
        tool_choice={"type": "tool", "name": _ROUTER_TOOL_NAME},
        messages=[{"role": "user", "content": query}],
        timeout=_CLAUDE_TIMEOUT_S,
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and isinstance(block.input, dict):
            return block.input
    return {}


async def _classify(query: str) -> dict:
    mode = _structured_mode()
    if mode != "off":
        try:
            parsed = await (_classify_ilmu_schema(query) if mode == "ilmu_schema" else _classify_claude_tool(query))
            if parsed:
                return parsed
            log.warning("router_structured_empty", mode=mode)
        except CircuitOpenError:
            if mode == "ilmu_schema":
                # The plain path shares ilmu_breaker, so falling back would only fail the same way.
                raise
            log.warning("router_claude_circuit_open")
        except Exception as exc:
            log.warning("router_structured_failed", mode=mode, error=str(exc))
    return await _classify_plain(query)


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
        parsed = await _classify(query)
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
    else:
        # The query's own words win over the LLM: ILMU has labelled plain
        # English questions "bm" (a MyKad question was then answered in
        # Bahasa Malaysia). Only overrides when the function words are
        # decisive; an ambiguous query keeps the LLM's label.
        detected = detect_latin_language(query)
        if detected and detected != language:
            log.info("router_language_overridden", llm_language=language, detected=detected)
            language = detected

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
