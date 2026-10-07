"""ScamShield agent state — single-shot verdict on a pasted SMS/link/phone
number claiming to be from a Malaysian government agency or bank.

Same single-shot shape as welfare_eligibility_agent: one input, one
deterministic check, one LLM-explained result. No checkpointer needed.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

# "unverified" is the honest default, not "safe" — absence from
# official_gov_domains means the list doesn't cover it, not that it's
# confirmed legitimate. See check_node.py's docstring for why this
# distinction is the whole point of the feature.
Verdict = Literal["verified_official", "impersonation_risk", "unverified", "no_url_found"]


class ExtractedDomainCheck(TypedDict, total=False):
    url: str
    domain: str
    verdict: Verdict
    matched_institution: str | None  # set for verified_official and impersonation_risk
    matched_domain: str | None       # the real official domain being matched/mimicked


class ScamCheckState(TypedDict, total=False):
    session_id: str
    user_id: str | None
    language: str
    input_text: str                       # raw pasted SMS/message/URL as given
    checks: list[ExtractedDomainCheck]     # one entry per URL found in input_text
    overall_verdict: Verdict               # worst-case across checks (impersonation_risk wins over unverified wins over verified_official)
    text_red_flags: list[str]              # deterministic urgency/payment-request keyword hits, given to the LLM to explain — never invented by it
    summary: str
    error: str | None
    # Internal, stripped from any public-facing output (see agent_runner._public_output)
    _supabase: Any
