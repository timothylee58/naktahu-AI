"""intake_node — 3-turn conversational business-profile intake for the Eligibility Agent.

Turn 0: ask business type + sector.
Turn 1: ask revenue + employees + Bumiputera status.
Turn 2: ask Malaysia Digital status + existing grants held.
Turn 3+: intake considered complete once all required fields are present.
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from app.agents.eligibility_agent.state import BusinessProfile, EligibilityState
from app.agents.tools import llm_complete

log = structlog.get_logger(__name__)

_REQUIRED_FIELDS = (
    "business_type",
    "sector",
    "registered_months",
    "annual_revenue_myr",
    "is_bumiputera",
    "employee_count",
)

_QUESTIONS_EN = [
    "What type of business do you have (sole proprietorship, Sdn Bhd, startup, LLP, or cooperative), "
    "and what sector are you in?",
    "What is your annual revenue (RM) and how many employees do you have? Is your business Bumiputera-owned?",
    "Do you have Malaysia Digital (MD) status, and have you received any government grants before?",
]

_QUESTIONS_BM = [
    "Apakah jenis perniagaan anda (milikan tunggal, Sdn Bhd, startup, LLP, atau koperasi), "
    "dan apakah sektor perniagaan anda?",
    "Berapakah hasil tahunan (RM) perniagaan anda dan berapa ramai pekerja anda? "
    "Adakah perniagaan anda milik Bumiputera?",
    "Adakah anda mempunyai status Malaysia Digital (MD), dan pernahkah anda menerima geran kerajaan sebelum ini?",
]

_EXTRACTION_SYSTEM_PROMPT = """\
You extract structured business-profile fields from a Malaysian SME owner's free-text
answer during a grant-eligibility intake conversation. Return ONLY a JSON object with any
of these keys you can confidently infer from the text — omit keys you cannot infer,
never guess or fabricate a value:
business_type (one of sole_prop, sdn_bhd, startup, llp, cooperative),
registered_months (integer),
sector (short lowercase string, e.g. "technology", "fnb", "manufacturing"),
sub_sector (short lowercase string),
annual_revenue_myr (number, 0 if pre-revenue),
is_bumiputera (boolean),
employee_count (integer),
has_md_status (boolean),
existing_grants (list of programme name strings),
is_pre_revenue (boolean).
"""


def _missing_required(profile: dict[str, Any]) -> list[str]:
    return [f for f in _REQUIRED_FIELDS if profile.get(f) is None]


async def _extract_profile_fields(text: str, language: str) -> dict[str, Any]:
    """Best-effort LLM extraction of business-profile fields from free text."""
    raw = await llm_complete(
        _EXTRACTION_SYSTEM_PROMPT,
        text,
        language=language,
        max_tokens=300,
    )
    if not raw:
        return {}
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


async def intake_node(state: EligibilityState) -> dict[str, Any]:
    turn = state.get("current_turn", 0)
    language = state.get("language") or "en"
    profile: BusinessProfile = dict(state.get("business_profile") or {})  # type: ignore[assignment]
    user_input = state.get("latest_user_input", "")

    if turn > 0 and user_input:
        extracted = await _extract_profile_fields(user_input, language)
        profile.update({k: v for k, v in extracted.items() if v is not None})

    missing = _missing_required(profile)

    if not missing and turn >= 3:
        return {
            "business_profile": profile,
            "missing_fields": [],
            "intake_complete": True,
            "needs_more_info": False,
            "next_question": None,
            "current_turn": turn,
        }

    questions = _QUESTIONS_BM if language == "bm" else _QUESTIONS_EN
    idx = min(turn, len(questions) - 1)
    return {
        "business_profile": profile,
        "missing_fields": missing,
        "intake_complete": False,
        "needs_more_info": True,
        "next_question": questions[idx],
        "current_turn": turn + 1,
    }
