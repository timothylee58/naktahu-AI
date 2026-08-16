"""Welfare Eligibility Agent — explanation step, never a discovery step.

The LLM here explains schemes match_node already deterministically found
(or honestly reports that none were found / none are loaded yet) — it is
never asked to name a scheme itself. Same non-negotiable boundary as
eligibility_agent's grant summary: a hallucinated benefit scheme is a much
worse failure mode than a hallucinated grant, since it's read by someone
actually checking what welfare support they can get.
"""
from __future__ import annotations

from typing import Any

from app.agents.tools import llm_complete
from app.agents.welfare_eligibility_agent.state import WelfareState

_SYSTEM_PROMPT = """\
You are the explanation step of a Malaysian welfare/cost-of-living eligibility
checker. You are given a list of schemes a deterministic filter has ALREADY
matched to the user's profile — your only job is to explain, in plain
friendly language, why each one applies and what to do next (the source_url
given is where to apply/learn more). Do not name, describe, or imply the
existence of any scheme not in the given list — if the list is empty, say so
honestly and suggest checking the official Ihsan MADANI portal directly.
Never invent eligibility criteria, amounts, or agency names not given to you.
"""

_NO_SCHEMES_LOADED_BM = (
    "Ciri ini masih baharu — pangkalan data skim bantuan MADANI belum diisi lagi, "
    "jadi tiada padanan dapat dijana buat masa ini. Sila semak portal rasmi Ihsan MADANI "
    "(ihsanmadani.gov.my) secara langsung sementara ini."
)
_NO_SCHEMES_LOADED_EN = (
    "This feature is still new — the MADANI scheme database hasn't been populated yet, "
    "so no matches can be generated right now. Please check the official Ihsan MADANI "
    "portal (ihsanmadani.gov.my) directly in the meantime."
)


async def synthesiser_node(state: WelfareState) -> dict[str, Any]:
    language = state.get("language", "bm")
    schemes = state.get("matched_schemes") or []

    if state.get("no_schemes_loaded"):
        return {"summary": _NO_SCHEMES_LOADED_BM if language == "bm" else _NO_SCHEMES_LOADED_EN}

    if not schemes:
        no_match = (
            "Berdasarkan maklumat yang diberikan, tiada skim bantuan yang sepadan buat masa ini."
            if language == "bm"
            else "Based on the information given, no assistance schemes matched right now."
        )
        return {"summary": no_match}

    listing = "\n".join(
        f"- {s['scheme_name']} ({s['implementing_agency']}): {s['description']} "
        f"[{', '.join(s.get('match_reasons') or [])}] Source: {s['source_url']}"
        for s in schemes
    )
    summary = await llm_complete(
        _SYSTEM_PROMPT,
        f"Matched schemes:\n{listing}\n\nWrite a short, friendly summary for the user.",
        language=language,
    )
    return {"summary": summary}
