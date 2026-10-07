"""SME Compliance Navigator (PatuhiKu) — LangGraph nodes.

Router does multi-label keyword classification — tax, payroll, and corporate
can all fire from one query (e.g. "hired a foreign worker" triggers payroll's
EPF 2%/2% rule and is relevant to tax's EPF-relief note). Each triggered
domain gets its own Send()-dispatched subagent node, mirroring the fan-out
pattern already established in app/agents/research_synthesiser/graph.py
rather than compliance_drafter's sequential add_edge chain — these three
domains are independent enough to reason about in parallel, and Send() is the
LangGraph-native primitive for that, not asyncio.gather bolted on top.
"""
from __future__ import annotations

from typing import Any

import structlog
from langgraph.types import Send

from app.agents.sme_compliance_navigator.context import get_context
from app.agents.tools import llm_complete

log = structlog.get_logger(__name__)

_ALL_DOMAINS = ("tax", "payroll", "corporate")

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tax": (
        "revenue", "invoice", "e-invoice", "einvoice", "tax", "cukai", "lhdn",
        "stamp duty", "duti setem", "rm",
    ),
    "payroll": (
        "staff", "employee", "hire", "hired", "hiring", "pekerja", "worker",
        "epf", "kwsp", "socso", "eis", "payroll", "gaji", "salary", "foreign worker",
    ),
    "corporate": (
        "sdn bhd", "bhd", "company", "syarikat", "ssm", "incorporat", "annual return",
        "sole prop", "partnership", "director", "secretary",
    ),
}

_DOMAIN_LABELS = {
    "tax": "Tax (LHDN)",
    "payroll": "Payroll (EPF/SOCSO/EIS)",
    "corporate": "Corporate (SSM)",
}

_SUBAGENT_PROMPT = """\
You are the {domain_label} compliance subagent inside PatuhiKu, a Malaysian
SME compliance navigator. Given a business profile and a knowledge base,
identify which facts apply to THIS business specifically, and phrase each as
a short, dated action item where the knowledge gives a date/deadline/threshold.

Do not invent figures not present in the knowledge base. If a fact doesn't
clearly apply given the profile, omit it rather than including it "just in case."
Output plain text, one action item per line, no numbering, no preamble.
"""


def _detect_domains(business_profile: str) -> list[str]:
    text = business_profile.lower()
    triggered = [d for d in _ALL_DOMAINS if any(kw in text for kw in _DOMAIN_KEYWORDS[d])]
    return triggered or list(_ALL_DOMAINS)  # unclear profile -> check everything, don't go silent


async def router_node(state: dict[str, Any]) -> dict[str, Any]:
    """Multi-label classification: which domains does this business profile trigger."""
    domains = _detect_domains(state.get("business_profile") or "")
    return {"triggered_domains": domains, "domain_results": []}


def route_to_subagents(state: dict[str, Any]) -> list[Send]:
    profile = state.get("business_profile", "")
    language = state.get("language", "bm")
    return [
        Send("subagent_node", {"domain": d, "business_profile": profile, "language": language})
        for d in (state.get("triggered_domains") or [])
    ]


async def subagent_node(state: dict[str, Any]) -> dict[str, Any]:
    """Worker invoked once per Send() dispatch — reasons over one domain's static knowledge base."""
    domain = state.get("domain", "tax")
    profile = state.get("business_profile", "")
    language = state.get("language", "bm")

    context = get_context(domain)
    system = _SUBAGENT_PROMPT.format(domain_label=_DOMAIN_LABELS.get(domain, domain))
    user = f"Business profile: {profile}\n\n{context.as_prompt_block()}"
    reasoning = await llm_complete(system, user, language=language, max_tokens=400)

    return {
        "domain_results": [
            {
                "domain": domain,
                "label": _DOMAIN_LABELS.get(domain, domain),
                "reasoning": reasoning,
                "facts": context.facts,
                "sources": context.sources,
                "as_of": context.as_of.isoformat(),
                "is_stale": context.is_stale(),
            }
        ],
    }


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())[:60]


async def synthesizer_node(state: dict[str, Any]) -> dict[str, Any]:
    """Merge subagent outputs into one prioritized, deduped checklist.

    Prioritization is simple and deliberately transparent rather than another
    LLM call: corporate > tax > payroll, because SSM registration is a
    prerequisite that gates the other two (you can't file Form C or register
    as an employer without a registered entity first) — see corporate.md's
    "Notes for Agent Reasoning". Staleness warnings surface per-domain via
    AgentContext.is_stale() rather than being buried in prose, per the
    knowledge base's explicit design intent.
    """
    results = state.get("domain_results") or []
    domain_order = {"corporate": 0, "tax": 1, "payroll": 2}
    ordered = sorted(results, key=lambda r: domain_order.get(r.get("domain", ""), 99))

    checklist: list[dict[str, Any]] = []
    stale_warnings: list[str] = []
    seen_items: set[str] = set()

    for result in ordered:
        domain = result.get("domain", "")
        label = result.get("label", domain)
        lines = [ln.strip() for ln in (result.get("reasoning") or "").splitlines() if ln.strip()]
        for line in lines:
            key = _normalize(line)
            if not key or key in seen_items:
                continue
            seen_items.add(key)
            checklist.append({"domain": domain, "label": label, "item": line})

        if result.get("is_stale"):
            stale_warnings.append(
                f"This knowledge base ({label}) hasn't been reviewed since {result.get('as_of')} "
                f"— verify volatile figures before relying on it."
            )

    return {"checklist": checklist, "stale_warnings": stale_warnings}
