"""intake_node — business-profile intake for the Eligibility Agent.

The web form already collects the whole profile up front, so intake is
complete as soon as every required field is present — on the very first turn
when the form was filled in. Only when something is genuinely missing (e.g. a
caller that sends a partial profile) does it ask a follow-up, and that
follow-up names only the missing fields instead of replaying a fixed script.
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from app.agents.eligibility_agent import llm_split
from app.agents.eligibility_agent.state import BusinessProfile, EligibilityState
from app.agents.tools import llm_complete

log = structlog.get_logger(__name__)

# Only fields that change which grants match. annual_revenue_myr is optional on
# the form and the analyst already treats an unknown revenue as 0 (see
# analyst_node's `profile.get("annual_revenue_myr") or 0`). employee_count and
# has_md_status are not read by any matching or scoring code, so requiring them
# only forced users to answer questions that couldn't affect their results.
_REQUIRED_FIELDS = (
    "business_type",
    "sector",
    "registered_months",
    "is_bumiputera",
)

_LEAD = {
    "en": "Thanks. I just need a little more to match you:",
    "bm": "Terima kasih. Saya hanya perlukan sedikit maklumat lagi untuk memadankan anda:",
    "zh": "谢谢。还需要补充以下信息才能为您匹配：",
}

# One short prompt per field, so a follow-up asks only about what is missing.
_FIELD_PROMPTS = {
    "en": {
        "business_type": "What type of business is it (sole proprietorship, Sdn Bhd, startup, LLP, or cooperative)?",
        "sector": "Which sector are you in?",
        "registered_months": "How many months has the business been registered?",
        "is_bumiputera": "Is your business Bumiputera-owned?",
    },
    "bm": {
        "business_type": "Apakah jenis perniagaan anda (milikan tunggal, Sdn Bhd, startup, LLP, atau koperasi)?",
        "sector": "Apakah sektor perniagaan anda?",
        "registered_months": "Berapa bulan perniagaan anda telah didaftarkan?",
        "is_bumiputera": "Adakah perniagaan anda milik Bumiputera?",
    },
    "zh": {
        "business_type": "您经营的是哪种类型的企业（独资经营、私人有限公司 Sdn Bhd、初创企业、有限责任合伙 LLP 或合作社）？",
        "sector": "所属行业是什么？",
        "registered_months": "企业已注册多少个月？",
        "is_bumiputera": "企业是否为土著（Bumiputera）所有？",
    },
}


def _follow_up_question(missing: list[str], language: str) -> str:
    lang = language if language in _FIELD_PROMPTS else "en"
    prompts = _FIELD_PROMPTS[lang]
    return " ".join([_LEAD[lang], *(prompts[f] for f in missing)])


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


_PROFILE_KEYS = (
    "business_type", "registered_months", "sector", "sub_sector", "annual_revenue_myr",
    "is_bumiputera", "employee_count", "has_md_status", "existing_grants", "is_pre_revenue",
)


def _missing_required(profile: dict[str, Any]) -> list[str]:
    return [f for f in _REQUIRED_FIELDS if profile.get(f) is None]


def _parse_fields(raw: str) -> dict[str, Any]:
    """The first JSON object in an LLM reply, or {} if there is none we can use."""
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


async def _extract_profile_fields(text: str, language: str) -> dict[str, Any]:
    """Best-effort LLM extraction of business-profile fields from free text."""
    # Nemotron fast model first when enabled. It returns "" on any failure, and a
    # reply that yields no usable fields (chatter, malformed JSON, not an object,
    # or an empty object) is treated the same way: fall through to the existing
    # ILMU path rather than drop the turn. With the flag off this is exactly the
    # old behaviour.
    fields = _parse_fields(await llm_split.fast_complete(_EXTRACTION_SYSTEM_PROMPT, text, max_tokens=300))
    if any(fields.get(k) is not None for k in _PROFILE_KEYS):
        return fields
    raw = await llm_complete(
        _EXTRACTION_SYSTEM_PROMPT,
        text,
        language=language,
        max_tokens=300,
    )
    return _parse_fields(raw) if raw else {}


async def intake_node(state: EligibilityState) -> dict[str, Any]:
    turn = state.get("current_turn", 0)
    language = state.get("language") or "en"
    profile: BusinessProfile = dict(state.get("business_profile") or {})  # type: ignore[assignment]
    user_input = state.get("latest_user_input", "")

    if turn > 0 and user_input:
        extracted = await _extract_profile_fields(user_input, language)
        profile.update({k: v for k, v in extracted.items() if v is not None})

    missing = _missing_required(profile)

    if not missing:
        return {
            "business_profile": profile,
            "missing_fields": [],
            "intake_complete": True,
            "needs_more_info": False,
            "next_question": None,
            "current_turn": turn,
        }

    return {
        "business_profile": profile,
        "missing_fields": missing,
        "intake_complete": False,
        "needs_more_info": True,
        "next_question": _follow_up_question(missing, language),
        "current_turn": turn + 1,
    }
