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


def sanitise_query(raw: str) -> str:
    """Return cleaned query string or raise 422 HTTPException."""
    # Normalise unicode to NFC
    text = unicodedata.normalize("NFC", raw)
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
    return text
