"""Drafts a short, shareable social caption for an already-generated
answer — the "prepare content for a human to post" half of the
sharing/distribution feature (see routers/share.py for the permalink
half). This module never posts anything anywhere: it returns text for
the frontend to show the user, who copies it and pastes it into
WhatsApp/Telegram/Facebook themselves. No platform API, no login, no
scheduling — see the module's own callers for why that's a deliberate
boundary, not a missing feature.

Same ILMU-primary/Anthropic-fallback shape as services/translate.py.
"""
from __future__ import annotations

import structlog

from app.services.llm_client import FALLBACK_MODEL, ILMU_CHAT_MODEL, anthropic_client, ilmu_client

log = structlog.get_logger(__name__)

_LANGUAGE_NAMES = {
    "bm": "Bahasa Malaysia",
    "en": "English",
    "zh": "Simplified Chinese (Mandarin)",
}

_MAX_ANSWER_CHARS_IN_PROMPT = 1500


def _system_prompt(language: str) -> str:
    lang_name = _LANGUAGE_NAMES.get(language, language)
    return (
        f"You write a short, shareable social media caption in {lang_name} "
        "for a Malaysian civic-knowledge answer, so a reader can post it to "
        "a WhatsApp group, Telegram, or Facebook. Rules:\n"
        "- 2-4 sentences maximum, plain conversational tone, no hashtags, no emoji spam (one emoji at most).\n"
        "- Summarise the ANSWER's actual conclusion — never invent a fact, "
        "figure, or claim that isn't already in the answer given.\n"
        "- End by inviting the reader to check the linked source(s) themselves — "
        "this is not official government advice.\n"
        "- Output ONLY the caption text, nothing else (no preamble, no quotes around it)."
    )


async def draft_share_caption(query: str, answer: str, language: str = "en") -> str:
    """Returns a short caption, or "" on total failure — the caller
    degrades to "just share the link" rather than blocking sharing on
    this being available."""
    system = _system_prompt(language)
    user_content = f"Question asked: {query}\n\nAnswer given: {answer[:_MAX_ANSWER_CHARS_IN_PROMPT]}"

    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=200,
            temperature=0.3,
        )
        caption = (resp.choices[0].message.content or "").strip()
        if caption:
            return caption
    except Exception as exc:
        log.warning("share_caption_ilmu_failed", error=str(exc))

    try:
        resp = await anthropic_client.messages.create(
            model=FALLBACK_MODEL,
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()
    except Exception as exc:
        log.warning("share_caption_anthropic_fallback_failed", error=str(exc))
        return ""
