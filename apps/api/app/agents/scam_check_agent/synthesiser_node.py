"""ScamShield agent — explanation step, never a verdict step.

The LLM here explains a verdict check_node ALREADY reached deterministically
— it never decides whether a domain is official, and it never invents red
flags beyond what text_red_flags already found. Same non-negotiable
boundary as welfare_eligibility_agent's synthesiser_node, but with a worse
failure mode if violated: telling someone a scam link is "safe" can cost
them money directly, not just misinform them.
"""
from __future__ import annotations

from typing import Any

from app.agents.scam_check_agent.state import ScamCheckState
from app.agents.tools import llm_complete

_SYSTEM_PROMPT = """\
You are the explanation step of a Malaysian scam-check tool (ScamShield). You
are given a deterministic verdict for each URL found in the user's pasted
text, and a list of red-flag signals already detected in the text — your
only job is to explain these plainly and give practical next-step advice.

Rules you must never break:
- Never state or imply a URL is official/safe unless its verdict is
  "verified_official". Never state or imply a URL is fake/malicious unless
  its verdict is "impersonation_risk".
- For "unverified" URLs, say clearly that it could not be confirmed either
  way (not on the reference list) — never call it safe, never call it fake.
- Never invent additional red flags, institution names, or scam patterns
  beyond what you were given.
- If impersonation_risk is present, advise the user not to click the link
  or provide any information, and to verify directly via the real
  institution's known official channel instead.
"""

_NO_URL_BM = (
    "Tiada pautan (link) dikesan dalam teks yang diberikan. Jika anda menerima panggilan telefon "
    "atau mesej tanpa pautan yang mendesak anda membuat pembayaran atau berikan maklumat peribadi, "
    "sila sahkan terus melalui saluran rasmi agensi berkenaan sebelum bertindak."
)
_NO_URL_EN = (
    "No link was detected in the text given. If you received a call or message without a link "
    "pressuring you to pay or share personal information, verify directly through the institution's "
    "official channel before acting on it."
)


async def synthesiser_node(state: ScamCheckState) -> dict[str, Any]:
    language = state.get("language", "bm")
    checks = state.get("checks") or []
    red_flags = state.get("text_red_flags") or []
    overall = state.get("overall_verdict", "no_url_found")

    if overall == "no_url_found":
        return {"summary": _NO_URL_BM if language == "bm" else _NO_URL_EN}

    checks_listing = "\n".join(
        f"- {c['url']}: verdict={c['verdict']}"
        + (f", matches official {c['matched_institution']} ({c['matched_domain']})" if c.get("matched_institution") else "")
        for c in checks
    )
    flags_listing = ", ".join(red_flags) if red_flags else "none detected"

    summary = await llm_complete(
        _SYSTEM_PROMPT,
        f"URL checks:\n{checks_listing}\n\nText red flags: {flags_listing}\n\n"
        "Write a short, clear explanation and next-step advice for the user.",
        language=language,
    )
    if not summary:
        # llm_complete degrades to "" on failure — fall back to the raw
        # verdict facts rather than silently returning nothing, since this
        # is the one place a blank response is actively unhelpful.
        summary = checks_listing
    return {"summary": summary}
