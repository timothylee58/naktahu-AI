"""Property Concierge nodes — conversational buyer/renter intake + property
RAG + deterministic lead-tier scoring.

Scope note (see PR body / conversation this shipped from): this agent does
NOT source or recommend real listings, and does NOT place any live
WhatsApp/call outreach to agencies. Neither a listings inventory nor a
messaging/telephony provider exists in this codebase or session — inventing
either would mean fabricating data or standing up a new external
dependency without the architecture decision that requires (CLAUDE.md
§8). What it does do, honestly: qualify a lead against a deterministic
tier (score_lead — pure function, not LLM output, same "never let the LLM
compute the fact that matters" discipline as
retrenchment_navigator.calculate_statutory_benefits), surface real
property-domain RAG citations (tenancy, strata, land-title guidance), and
generate a ready-to-send brief the *user* can forward via their own
WhatsApp client (a wa.me deep link — client-initiated, no credentials, no
backend telephony — same pattern already used by profile/page.tsx's
referral-sharing button).
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.property_concierge.state import PropertyConciergeState
from app.agents.tools import llm_complete, query_rag_findings

_MAX_TURNS = 6

_RENT_WORDS = ("rent", "sewa", "lease", "menyewa", "tenancy")
_BUY_WORDS = ("buy", "beli", "purchase", "membeli", "purchasing")
_CONDO_WORDS = ("condo", "condominium", "kondominium", "serviced residence")
_APARTMENT_WORDS = ("apartment", "pangsapuri", "flat")
_LANDED_WORDS = ("landed", "terrace", "teres", "semi-d", "semi d", "bungalow", "link house", "rumah teres")

_DEFAULT_CHECKLIST = [
    "Shortlist 3-5 listings that match your criteria and compare price-per-sqft against nearby transactions.",
    "Verify the agent's REN (Registered Estate Agent) tag number before any viewing.",
    "Bring your own checklist to the viewing: water pressure, cell reception, parking, and maintenance fee history.",
    "For a purchase: check the land title type (freehold/leasehold) and any outstanding caveats before booking.",
    "For a rental: confirm the deposit structure (2 months + 0.5 month utility is standard) in writing before paying.",
]
_DEFAULT_WARNINGS = [
    "Never transfer a booking fee or deposit before an in-person or verified video viewing.",
    "A price that looks well below market for the area is the most common scam signal — verify against recent transacted prices, not just other listings.",
    "This tool does not source live listings or contact agencies on your behalf — use the brief below to reach out yourself.",
]


def _extract_number(text: str, patterns: list[str]) -> float | None:
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def score_lead(
    purpose: str | None,
    location: str | None,
    budget_myr: float | None,
    property_type: str | None,
    bedrooms: int | None,
) -> str:
    """Deterministic lead-qualification tier — pure function, no LLM."""
    if purpose and location and budget_myr and budget_myr > 0:
        return "hot" if (property_type and bedrooms) else "warm"
    return "cold"


async def intake_node(state: PropertyConciergeState) -> dict[str, Any]:
    turns = int(state.get("turns_count") or 0) + 1
    messages = list(state.get("messages") or [])
    latest = state.get("message") or ""
    if latest:
        messages.append(latest)
    combined = " ".join(messages)
    lower = combined.lower()

    purpose = state.get("purpose")
    if purpose is None:
        if any(w in lower for w in _RENT_WORDS):
            purpose = "rent"
        elif any(w in lower for w in _BUY_WORDS):
            purpose = "buy"

    property_type = state.get("property_type")
    if property_type is None:
        if any(w in lower for w in _CONDO_WORDS):
            property_type = "condo"
        elif any(w in lower for w in _APARTMENT_WORDS):
            property_type = "apartment"
        elif any(w in lower for w in _LANDED_WORDS):
            property_type = "landed"

    budget_myr = state.get("budget_myr")
    if budget_myr is None:
        budget_myr = _extract_number(
            combined, [r"(?:rm|myr)\s*([\d,]+(?:\.\d+)?)", r"([\d,]+(?:\.\d+)?)\s*(?:ringgit|budget)"]
        )

    bedrooms = state.get("bedrooms")
    if bedrooms is None:
        n = _extract_number(combined, [r"(\d+)\s*(?:bedroom|bilik tidur|bilik)"])
        bedrooms = int(n) if n is not None else None

    location = state.get("location")
    if location is None:
        m = re.search(r"(?:in|at|di|kawasan|near)\s+([A-Za-z\s]{2,40})", latest, re.IGNORECASE)
        if m:
            location = m.group(1).strip().rstrip(".,!?")
        elif purpose is not None and budget_myr is not None and latest.strip():
            # Nothing else matched this turn, and the only thing still
            # missing by the time purpose+budget are both known is the
            # location prompt below — so treat the raw reply as the answer.
            location = latest.strip().rstrip(".,!?")[:80]

    missing: list[str] = []
    if purpose is None:
        missing.append("purpose")
    if budget_myr is None:
        missing.append("budget")
    if location is None:
        missing.append("location")

    intake_complete = not missing or turns >= _MAX_TURNS
    next_prompt: str | None = None
    if not intake_complete:
        if "purpose" in missing:
            next_prompt = "Are you looking to buy or rent? / Anda mahu beli atau sewa?"
        elif "budget" in missing:
            next_prompt = "What's your budget (RM)? / Berapakah bajet anda (RM)?"
        else:
            next_prompt = "Which area or state are you looking in? / Kawasan atau negeri mana yang anda cari?"

    return {
        "messages": messages,
        "purpose": purpose,
        "property_type": property_type,
        "location": location,
        "budget_myr": budget_myr,
        "bedrooms": bedrooms,
        "intake_complete": intake_complete,
        "next_prompt": next_prompt,
        "turns_count": turns,
        "status": "needs_input" if not intake_complete else "intake_done",
    }


async def property_rag_node(state: PropertyConciergeState) -> dict[str, Any]:
    lang = state.get("language") or "bm"
    query = (
        f"{state.get('property_type') or 'property'} {state.get('purpose') or ''} "
        f"{state.get('location') or ''} Malaysia tenancy strata land title guidance"
    )
    findings = await query_rag_findings(query, "property", lang)
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "query_rag", "domain": "property", "hops": 1})
    return {"_rag_findings": findings, "tool_calls": tool_calls}


async def output_node(state: PropertyConciergeState) -> dict[str, Any]:
    findings = state.get("_rag_findings") or []
    lang = state.get("language") or "bm"
    context = "\n".join(f"- {f['summary']}" for f in findings[:4])

    purpose = state.get("purpose")
    location = state.get("location")
    budget = state.get("budget_myr")
    property_type = state.get("property_type")
    bedrooms = state.get("bedrooms")

    lead_tier = score_lead(purpose, location, budget, property_type, bedrooms)
    search_criteria = {
        "purpose": purpose,
        "property_type": property_type,
        "location": location,
        "budget_myr": budget,
        "bedrooms": bedrooms,
    }

    raw = await llm_complete(
        "You are a Malaysian property concierge assistant. Given a buyer/renter's "
        "criteria, return JSON with keys: checklist (array of strings, viewing/"
        "paperwork prep specific to their purpose and property type) and warnings "
        "(array of strings, scam-safety or process cautions). Do not invent listing "
        "prices, addresses, or agency names — none were provided.",
        f"Purpose: {purpose}\nProperty type: {property_type}\nLocation: {location}\n"
        f"Budget: RM{budget}\nBedrooms: {bedrooms}\nSources:\n{context}",
        language=lang,
    )
    checklist = list(_DEFAULT_CHECKLIST)
    warnings = list(_DEFAULT_WARNINGS)
    if raw:
        try:
            parsed = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            checklist = parsed.get("checklist") or checklist
            warnings = parsed.get("warnings") or warnings
        except (json.JSONDecodeError, ValueError):
            pass

    citations = [
        {
            "title": f.get("source_title", ""),
            "url": f.get("source_url", ""),
            "ministry": f.get("domain", "property"),
            "confidence": float(f.get("similarity", 0.7)),
        }
        for f in findings[:3]
        if f.get("source_url")
    ]

    escalation_message = (
        f"Looking to {purpose or 'find'} a {property_type or 'property'}"
        f"{f' ({bedrooms} bedroom)' if bedrooms else ''} in {location or 'Malaysia'}, "
        f"budget RM{budget:,.0f}. Please let me know what's available." if budget else
        f"Looking to {purpose or 'find'} a {property_type or 'property'} in {location or 'Malaysia'}."
    )

    return {
        "lead_tier": lead_tier,
        "search_criteria": search_criteria,
        "checklist": checklist,
        "warnings": warnings,
        "escalation_message": escalation_message,
        "citations": citations,
        "status": "completed",
    }


def route_after_intake(state: PropertyConciergeState) -> str:
    if state.get("intake_complete"):
        return "property_rag"
    return "__end__"
