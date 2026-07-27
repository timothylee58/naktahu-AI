"""synthesiser_node — streams the final eligibility summary as SSE-shaped dict events.

Provider order matches CLAUDE.md hard rule: ILMU primary, Anthropic
(claude-sonnet-4-20250514) fallback for synthesis only.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator

import structlog

from app.agents.eligibility_agent.state import EligibilityState
from app.services.llm_client import FALLBACK_MODEL, ILMU_CHAT_MODEL, anthropic_client, ilmu_client

log = structlog.get_logger(__name__)

_LANG_INSTRUCTION = {
    "bm": "PENTING: Jawab dalam Bahasa Malaysia sahaja.",
    "en": "IMPORTANT: Answer in English only.",
}

_SYSTEM_PROMPT = (
    "You are the Eligibility Agent inside NakTahu AI. Summarise, in 3-5 short paragraphs, "
    "which Malaysian government grants this SME qualifies for, why, and a suggested "
    "application order. Only reference grants explicitly given to you — never invent a "
    "programme name, amount, or deadline."
)


def _build_prompt(state: EligibilityState) -> str:
    profile = state.get("business_profile") or {}
    matched = state.get("matched_grants") or []
    near_miss = state.get("near_miss_grants") or []
    matrix = state.get("stacking_matrix") or {}

    lines = [f"Business profile: {profile}", "", "Matched grants:"]
    for g in matched:
        lines.append(f"- {g.get('programme_name')} ({g.get('agency')}): RM{g.get('amount_min_myr')}-{g.get('amount_max_myr')}")
    if near_miss:
        lines.append("")
        lines.append("Near-miss grants (almost eligible):")
        for g in near_miss:
            lines.append(f"- {g.get('programme_name')}: {g.get('ineligibility_reasons')}")
    if matrix:
        lines.append("")
        lines.append(f"Recommended application sequence: {matrix.get('recommended_sequence')}")
        lines.append(f"Conflicting pairs: {matrix.get('conflict_pairs')}")
    return "\n".join(lines)


async def _stream_ilmu(prompt: str, system_prompt: str) -> AsyncGenerator[str, None]:
    stream = await ilmu_client.chat.completions.create(
        model=ILMU_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        stream=True,
        max_tokens=700,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def _stream_anthropic(prompt: str, system_prompt: str) -> AsyncGenerator[str, None]:
    async with anthropic_client.messages.stream(
        model=FALLBACK_MODEL,
        max_tokens=700,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def synthesiser_node(state: EligibilityState) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator of SSE-shaped events: token* -> grant* -> stacking -> metadata -> done."""
    language = state.get("language") or "en"
    system_prompt = f"{_LANG_INSTRUCTION.get(language, _LANG_INSTRUCTION['en'])}\n\n{_SYSTEM_PROMPT}"
    prompt = _build_prompt(state)

    buffer = ""
    try:
        async for token in _stream_ilmu(prompt, system_prompt):
            buffer += token
            yield {"type": "token", "text": token}
    except Exception as exc:
        log.warning("eligibility_ilmu_stream_failed_falling_back", error=str(exc))
        try:
            async for token in _stream_anthropic(prompt, system_prompt):
                buffer += token
                yield {"type": "token", "text": token}
        except Exception as exc2:
            log.error("eligibility_synthesis_failed", error=str(exc2))
            yield {"type": "error", "message": "Synthesis failed. Please try again."}
            return

    for g in state.get("matched_grants") or []:
        yield {"type": "grant", "data": g}

    matrix = state.get("stacking_matrix")
    if matrix:
        yield {"type": "stacking", "data": matrix}

    yield {
        "type": "metadata",
        "data": {
            "matched_count": len(state.get("matched_grants") or []),
            "near_miss_count": len(state.get("near_miss_grants") or []),
        },
    }
    yield {"type": "done"}
