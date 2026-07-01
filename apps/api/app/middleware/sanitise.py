"""Input sanitisation for the query endpoint.

Validates query length and strips control characters before they reach the
LangGraph pipeline. Raises HTTPException 422 on policy violations so the
client receives a structured error, not a 500.
"""
from __future__ import annotations

import re
import unicodedata

from fastapi import HTTPException

_MAX_QUERY_LEN = 1000
_MIN_QUERY_LEN = 2
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Supplementary confusables map for homoglyphs NOT folded by NFKC.
# NFKC already handles full-width ASCII (U+FF01-U+FF5E) and many ligatures,
# so we only need to cover cross-script lookalikes (e.g. Cyrillic) that are
# "correct" letters in their own script and therefore untouched by NFKC.
# This map is used ONLY to build a detection copy for the injection-pattern
# scan below — it is never applied to the text that gets returned/forwarded
# to the LLM pipeline, so legitimate non-Latin script queries (bm/zh) are
# never mangled.
_CONFUSABLES_MAP = {
    # Cyrillic lowercase lookalikes -> Latin
    "а": "a",  # а CYRILLIC SMALL LETTER A
    "е": "e",  # е CYRILLIC SMALL LETTER IE
    "о": "o",  # о CYRILLIC SMALL LETTER O
    "р": "p",  # р CYRILLIC SMALL LETTER ER
    "с": "c",  # с CYRILLIC SMALL LETTER ES
    "х": "x",  # х CYRILLIC SMALL LETTER HA
    "і": "i",  # і CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    # Cyrillic uppercase lookalikes -> Latin
    "А": "A",  # А
    "Е": "E",  # Е
    "О": "O",  # О
    "Р": "P",  # Р
    "С": "C",  # С
    "Х": "X",  # Х
    "І": "I",  # І
}
_CONFUSABLES_RE = re.compile("|".join(re.escape(k) for k in _CONFUSABLES_MAP))


def _fold_confusables(text: str) -> str:
    """Return a copy of text with high-risk homoglyphs folded to Latin.

    Used only to build a detection-time copy for the injection regex scan.
    """
    return _CONFUSABLES_RE.sub(lambda m: _CONFUSABLES_MAP[m.group(0)], text)

# Prompt injection patterns — catch common jailbreak attempts
#
# Exposed publicly as INJECTION_PATTERNS so other modules (e.g. the
# synthesiser_node output-side scan) can reuse the same compiled pattern
# list instead of duplicating it.
INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|constraints?)",
        r"forget\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|training|rules?)",
        r"you\s+are\s+now\s+(a\s+)?(?!NakTahu)",
        r"act\s+as\s+(if\s+you\s+are\s+)?(?!a\s+Malaysian)",
        r"pretend\s+(you\s+are|to\s+be)",
        r"do\s+anything\s+now",
        r"jailbreak",
        r"dan\s+mode",  # "DAN mode"
        r"developer\s+mode",
        r"system\s*:\s*you\s+are",
        r"<\s*/?system\s*>",
        r"\[INST\]|\[\/INST\]",  # Llama instruction tokens
        r"###\s*instruction",
        r"---\s*new\s*(system\s*)?prompt",
        r"disregard\s+(your\s+)?(previous\s+)?(instructions?|guidelines?|rules?)",
        r"override\s+(your\s+)?(instructions?|guidelines?|safety)",
    ]
]

# Backwards-compatible private alias (kept in case other internal code
# still imports the old private name).
_INJECTION_PATTERNS = INJECTION_PATTERNS


def _check_injection(text: str) -> None:
    """Raise 422 if the query contains prompt injection patterns.

    Scans a homoglyph-folded copy of `text` so lookalike-character evasion
    (e.g. Cyrillic "і" for Latin "i") cannot bypass the regexes below. The
    caller is responsible for forwarding the original, non-folded text to
    the pipeline — this function only inspects, it never mutates.
    """
    detection_text = _fold_confusables(text)
    for pattern in INJECTION_PATTERNS:
        if pattern.search(detection_text):
            raise HTTPException(
                status_code=422,
                detail="Query contains disallowed content.",
            )


def sanitise_query(raw: str) -> str:
    """Return cleaned query string or raise 422 HTTPException."""
    # Normalise unicode to NFKC: canonicalizes compatibility characters
    # (full-width -> half-width, ligatures, etc.) before the injection scan
    # runs, so those forms can't be used to dodge the regex patterns.
    text = unicodedata.normalize("NFKC", raw)
    # Strip leading/trailing whitespace
    text = text.strip()
    # Remove ASCII control characters (keep \t \n \r)
    text = _CONTROL_CHAR_RE.sub("", text)
    # Collapse internal whitespace runs
    text = re.sub(r"[ \t]{2,}", " ", text)

    if len(text) < _MIN_QUERY_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"Query too short (minimum {_MIN_QUERY_LEN} characters).",
        )
    if len(text) > _MAX_QUERY_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"Query too long (maximum {_MAX_QUERY_LEN} characters).",
        )

    # Detection uses a homoglyph-folded copy; the text returned/forwarded
    # to the LLM pipeline is the NFKC-normalised original (not the folded
    # copy), so legitimate non-Latin script queries are never mangled.
    _check_injection(text)
    return text
