"""Research Synthesiser — parallel RAG fan-out via LangGraph Send() API,
now followed by a real cross-domain synthesis step.

Scale-up from the original version: that version only aggregated and
deduplicated raw citations across up to 3 domains — no narrative text at
all, despite the agent's name. It also only recognised 3 of the 13
canonical domains (finance/government/education via a few hardcoded
keywords) and silently defaulted everything else to a fixed
government+finance+legal triple, which is wrong for e.g. a healthcare or
immigration question. Both gaps are fixed here:

1. `_detect_domains` now covers all 13 canonical domains via the same
   `_DOMAIN_ALIASES`-style keyword approach router_node.py uses (kept as
   its own lightweight copy rather than importing router_node directly —
   that module pulls in the full LLM router path and the streaming SSE
   contract, which this single-shot JSON-response agent doesn't use).
2. New `synthesis_node`: an actual LLM call (ILMU primary, Anthropic
   fallback — CLAUDE.md hard rule on provider order) that reads the
   deduplicated findings' excerpt text (not just titles/URLs) and writes
   a short cross-domain narrative in the query's language. Same
   provider-order/never-fabricate discipline every other synthesiser in
   this codebase follows — grounded strictly in the findings passed to it.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

from app.agents.tools import query_rag_findings
from app.services.llm_client import FALLBACK_MODEL, ILMU_CHAT_MODEL, anthropic_client, ilmu_client

log = structlog.get_logger(__name__)

_MAX_DOMAINS = 3

# Same canonical set as router_node.py's _VALID_DOMAINS (Trap #6) —
# duplicated here rather than imported for the reason in the module
# docstring above. Any change to the canonical list touches both sites.
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tax": ("cukai", "tax", "lhdn", "sst", "e-filing"),
    "epf": ("epf", "kwsp", "socso", "perkeso", "eis", "pencen", "retirement"),
    "government": ("kerajaan", "government", "public service", "perkhidmatan awam"),
    "education": ("pendidikan", "education", "spm", "sekolah", "school", "ptptn", "university", "universiti"),
    "business": ("ssm", "syarikat", "business", "company", "perniagaan", "geran", "grant"),
    "healthcare": ("kesihatan", "health", "hospital", "klinik", "clinic", "kkm"),
    "legal": ("undang-undang", "legal", "law", "mahkamah", "court", "termination", "pemberhentian"),
    "immigration": ("imigresen", "immigration", "visa", "pasport", "passport", "mykad"),
    "culture": ("budaya", "culture", "warisan", "heritage", "motac"),
    "parliament": ("parlimen", "parliament", "ahli parlimen", "mp ", "hansard", "undi", "vote"),
    "property": ("tanah", "hartanah", "property", "strata", "sewa", "tenancy"),
    "welfare": ("bantuan", "welfare", "kebajikan", "subsidi", "rebate", "rahmah"),
    "finance": ("kewangan", "finance", "bank", "pinjaman", "loan"),
}


class ResearchState(TypedDict, total=False):
    query: str
    language: str
    detected_domains: list[str]
    domain_results: Annotated[list[dict[str, Any]], operator.add]
    merged_citations: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    summary: str
    # Internal only — excerpt text synthesis_node needs but the API
    # response never returns (agent_runner.py's response dict whitelists
    # fields explicitly, so this key is naturally excluded).
    _findings_with_excerpts: list[dict[str, Any]]


def _detect_domains(query: str) -> list[str]:
    lowered = query.lower()
    hits = [domain for domain, kws in _DOMAIN_KEYWORDS.items() if any(kw in lowered for kw in kws)]
    if not hits:
        # No keyword matched anything — fall back to the 3 broadest
        # civic domains rather than guessing a specific one, same
        # reasoning router_node.py uses for its own None-domain default.
        return ["government", "finance", "legal"]
    return hits[:_MAX_DOMAINS]


async def router_domains_node(state: ResearchState) -> dict[str, Any]:
    """Detect which RAG domains to fan out to (max 3)."""
    domains = _detect_domains(state.get("query") or "")
    return {"detected_domains": domains, "domain_results": []}


def route_to_domains(state: ResearchState) -> list[Send]:
    return [
        Send("rag_node", {"query": state.get("query", ""), "domain": d, "language": state.get("language", "bm")})
        for d in (state.get("detected_domains") or [])
    ]


async def rag_domain_node(state: dict[str, Any]) -> dict[str, Any]:
    domain = state.get("domain", "government")
    query = state.get("query", "")
    language = state.get("language", "bm")
    findings = await query_rag_findings(query, domain, language)
    return {"domain_results": [{"domain": domain, "findings": findings}]}


def _merge_findings(state: ResearchState) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (public_citations, findings_with_excerpts) — the second list
    keeps the excerpt text (findings' own "summary" field) that
    synthesis_node needs but citations shown to the user don't."""
    seen_urls: set[str] = set()
    citations: list[dict[str, Any]] = []
    findings_with_excerpts: list[dict[str, Any]] = []
    for block in state.get("domain_results") or []:
        for f in block.get("findings") or []:
            url = f.get("source_url") or ""
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            citations.append({
                "title": f.get("source_title", ""),
                "url": url,
                "ministry": f.get("domain", ""),
                "confidence": float(f.get("similarity", 0.0) if "similarity" in f else 0.7),
            })
            findings_with_excerpts.append({
                "domain": f.get("domain", ""),
                "title": f.get("source_title", ""),
                "excerpt": f.get("summary", ""),
            })
    return citations[:9], findings_with_excerpts[:9]


async def merge_node(state: ResearchState) -> dict[str, Any]:
    """Deduplicate citations across parallel domain results."""
    citations, findings_with_excerpts = _merge_findings(state)
    return {
        "merged_citations": citations,
        "citations": citations,
        # Threaded through to synthesis_node only — never returned to the
        # API response (agent_runner.py's response dict whitelists fields
        # explicitly; this key just isn't one of them).
        "_findings_with_excerpts": findings_with_excerpts,
    }


_LANG_INSTRUCTION = {
    "bm": "PENTING: Tulis sepenuhnya dalam Bahasa Malaysia.",
    "zh": "重要：请完全用简体中文撰写。",
    "en": "IMPORTANT: Write entirely in English.",
}

_SYSTEM_PROMPT = (
    "You are the Research Synthesiser inside NakTahu AI. You are given a research "
    "question and a set of excerpts pulled from official Malaysian government "
    "sources across several domains. Write a concise synthesis (3-5 short "
    "paragraphs, or fewer if the excerpts are thin) that connects what the "
    "excerpts actually say across domains — do not just restate each excerpt "
    "in a list. Only state facts present in the given excerpts; never invent a "
    "figure, date, or programme name. If the excerpts don't cover part of the "
    "question, say so plainly rather than filling the gap."
)


def _build_synthesis_prompt(query: str, findings: list[dict[str, Any]]) -> str:
    lines = [f"Research question: {query}", "", "Excerpts:"]
    for f in findings:
        excerpt = (f.get("excerpt") or "").strip()
        if not excerpt:
            continue
        lines.append(f"- [{f.get('domain', '')}] {f.get('title', '')}: {excerpt}")
    return "\n".join(lines)


async def synthesis_node(state: ResearchState) -> dict[str, Any]:
    """Real cross-domain narrative synthesis — ILMU primary, Anthropic
    fallback (CLAUDE.md hard rule on provider order for synthesis)."""
    findings = state.get("_findings_with_excerpts") or []
    query = state.get("query", "")
    language = state.get("language") or "en"

    if not findings:
        # Nothing retrieved — matches the frontend's existing "no results"
        # empty state; a synthesis call with zero grounding would just
        # invite fabrication, so skip it entirely rather than ask the LLM
        # to write around empty excerpts.
        return {"summary": ""}

    prompt = _build_synthesis_prompt(query, findings)
    system_prompt = f"{_LANG_INSTRUCTION.get(language, _LANG_INSTRUCTION['en'])}\n\n{_SYSTEM_PROMPT}"

    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=700,
        )
        summary = resp.choices[0].message.content or ""
    except Exception as exc:
        log.warning("research_synthesiser_ilmu_failed_falling_back", error=str(exc))
        try:
            resp = await anthropic_client.messages.create(
                model=FALLBACK_MODEL,
                max_tokens=700,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            summary = "".join(block.text for block in resp.content if block.type == "text")
        except Exception as fallback_exc:
            log.error("research_synthesiser_both_providers_failed", error=str(fallback_exc))
            # Degrade to "no narrative" rather than raising — citations are
            # still real and useful on their own (this mirrors the
            # pre-existing behaviour when nothing was synthesised at all).
            summary = ""

    return {"summary": summary}


def build_research_synthesiser_graph() -> StateGraph:
    graph = StateGraph(ResearchState)
    graph.add_node("router_node", router_domains_node)
    graph.add_node("rag_node", rag_domain_node)
    graph.add_node("merge_node", merge_node)
    graph.add_node("synthesis_node", synthesis_node)

    graph.add_edge(START, "router_node")
    graph.add_conditional_edges("router_node", route_to_domains, ["rag_node"])
    graph.add_edge("rag_node", "merge_node")
    graph.add_edge("merge_node", "synthesis_node")
    graph.add_edge("synthesis_node", END)
    return graph


_research_compiled: Any = None


def get_research_synthesiser_graph():
    global _research_compiled
    if _research_compiled is None:
        _research_compiled = build_research_synthesiser_graph().compile()
    return _research_compiled
