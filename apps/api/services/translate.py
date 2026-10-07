"""One-shot answer translation for the /chat page's translate control.

Distinct from the pipeline's own bilingual behaviour: router_node detects
the QUERY's language and synthesiser_node answers in that language — this
is a separate, on-demand action a user takes AFTER an answer already
exists, to read it in a different language than the one it was written
in. It never re-runs retrieval/synthesis and never touches document_chunks
or any other table — pure text-in, text-out.

Same ILMU-primary, Anthropic-fallback shape as app/agents/tools.py's
llm_complete/ocr_extract_text, imported here the same way
services/property_submissions.py already imports across the services/app
boundary (from app.agents.tools import ocr_extract_listing_fields).
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


def _system_prompt(target_language: str) -> str:
    target_name = _LANGUAGE_NAMES.get(target_language, target_language)
    return (
        f"Translate the user's text into {target_name}. Preserve markdown "
        "formatting (bold, lists, links) exactly as-is — translate only the "
        "visible text, never the markdown syntax or URLs. Do not add "
        "commentary, explanations, or a preamble like 'Here is the "
        "translation:' — output ONLY the translated text itself. If the "
        f"text is already in {target_name}, return it unchanged."
    )


async def translate_text(text: str, target_language: str) -> str:
    """Returns the translated text, or "" on total failure (both providers
    down) — same degrade-to-empty contract as ocr_extract_text, so the
    caller (the translate router) can turn that into a clean 502 instead
    of crashing."""
    system = _system_prompt(target_language)
    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            max_tokens=2000,
            temperature=0.0,
        )
        translated = (resp.choices[0].message.content or "").strip()
        if translated:
            return translated
    except Exception as exc:
        log.warning("translate_ilmu_failed", error=str(exc), target_language=target_language)

    try:
        resp = await anthropic_client.messages.create(
            model=FALLBACK_MODEL,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()
    except Exception as exc:
        log.warning("translate_anthropic_fallback_failed", error=str(exc), target_language=target_language)
        return ""
