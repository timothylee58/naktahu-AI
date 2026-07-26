"""Grant Finder nodes — match SMEs/students to government grants."""
from __future__ import annotations

import json
from typing import Any

from app.agents.grant_finder.state import GrantFinderState
from app.agents.tools import llm_complete, query_rag_findings
from app.services.grant_programmes import get_grant_programmes_by_urls


async def profile_node(state: GrantFinderState) -> dict[str, Any]:
    return {
        "sector": state.get("sector") or state.get("message", "")[:80] or "technology",
        "business_stage": state.get("business_stage") or "early",
        "funding_need": state.get("funding_need") or state.get("message") or "working capital",
        "language": state.get("language") or "bm",
    }


async def grant_rag_node(state: GrantFinderState) -> dict[str, Any]:
    lang = state.get("language") or "bm"
    q = (
        f"geran kerajaan Malaysia {state.get('sector')} {state.get('business_stage')} "
        f"{state.get('funding_need')} MDEC MATRADE Cradle TEKUN MARA"
    )
    gov = await query_rag_findings(q, "government", lang)
    fin = await query_rag_findings(f"pembiayaan {q}", "finance", lang)
    findings = gov + [f for f in fin if f.get("source_url") not in {g.get("source_url") for g in gov}]
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "query_rag", "domains": ["government", "finance"]})
    return {"_rag_findings": findings, "tool_calls": tool_calls}


async def match_node(state: GrantFinderState) -> dict[str, Any]:
    findings = state.get("_rag_findings") or []
    lang = state.get("language") or "bm"
    context = "\n".join(f"- {f['source_title']}: {f['summary'][:200]}" for f in findings[:5])
    raw = await llm_complete(
        "List up to 3 Malaysian government grants/schemes as JSON array: "
        "[{name, eligibility, amount_hint, deadline_hint, url}]",
        f"Profile: sector={state.get('sector')}, stage={state.get('business_stage')}, need={state.get('funding_need')}\n{context}",
        language=lang,
        max_tokens=600,
    )
    grants: list[dict[str, Any]] = []
    if raw:
        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                grants = json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
    if not grants:
        for i, f in enumerate(findings[:3]):
            grants.append({
                "name": f.get("source_title") or f"Scheme {i + 1}",
                "eligibility": "See official source",
                "amount_hint": "Varies",
                "deadline_hint": "Check agency website",
                "url": f.get("source_url", ""),
            })

    grants = await _enrich_with_structured_facts(grants)

    citations = [
        {"title": g.get("name", ""), "url": g.get("url", ""), "ministry": "Kerajaan Malaysia", "confidence": 0.7}
        for g in grants
        if g.get("url")
    ]
    return {"grants": grants, "citations": citations, "status": "completed"}


def _format_amount(programme: dict[str, Any]) -> str | None:
    amount = programme.get("grant_amount_myr")
    if amount is None:
        return None
    return f"Up to RM{amount:,.0f}" if float(amount) == int(amount) else f"Up to RM{amount:,.2f}"


async def _enrich_with_structured_facts(grants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Overlay real grant_programmes facts onto the LLM's amount_hint/
    deadline_hint text where a structured record exists for that URL —
    replaces a guess with a real figure instead of asking the model to
    invent one. Grants with no matching programme record are returned
    unchanged; this must never fabricate a match."""
    urls = [g.get("url", "") for g in grants if g.get("url")]
    programmes = await get_grant_programmes_by_urls(urls)
    if not programmes:
        return grants

    enriched: list[dict[str, Any]] = []
    for g in grants:
        programme = programmes.get(g.get("url", ""))
        if not programme:
            enriched.append(g)
            continue

        merged = dict(g)
        amount_text = _format_amount(programme)
        if amount_text:
            merged["amount_hint"] = amount_text
            merged["amount_myr"] = programme["grant_amount_myr"]
        if programme.get("application_deadline"):
            merged["deadline_hint"] = programme["application_deadline"]
            merged["deadline"] = programme["application_deadline"]
        if programme.get("eligible_sectors"):
            merged["eligible_sectors"] = programme["eligible_sectors"]
        if programme.get("bumiputera_requirement") is not None:
            merged["bumiputera_requirement"] = programme["bumiputera_requirement"]
        if programme.get("company_age_min_months") is not None:
            merged["company_age_min_months"] = programme["company_age_min_months"]
        merged["is_verified"] = True
        enriched.append(merged)

    return enriched
