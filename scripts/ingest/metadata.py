"""Freshness metadata helpers for the document_chunks ingestion pipeline.

Centralises the parsing/derivation of the freshness columns that
``analyst_node`` and the ``temporal_accuracy`` eval metric consume:

- ``effective_date`` — when the rule/figure a chunk describes takes effect.
- ``superseded_by`` — the chunk that replaces this one (hard-rejected at query
  time so it is never cited).

Pure-Python and dependency-free (stdlib only) so it can be unit-tested without
the heavy ingest deps (pycld2 / langchain / openai / supabase).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable, Optional

# Raw-file metadata header. SOURCE_DATE / EXPIRY_AWARE / EFFECTIVE_DATE /
# SUPERSEDES are optional and, when present, must appear in this order before
# the closing ``---``.
HEADER_RE = re.compile(
    r"SOURCE_TITLE:[ \t]*(.+)\n"
    r"SOURCE_URL:[ \t]*(.+)\n"
    r"MINISTRY:[ \t]*(.+)\n"
    r"DOMAIN:[ \t]*(.+)\n"
    r"(?:SOURCE_DATE:[ \t]*([^\n]*)\n)?"
    r"(?:EXPIRY_AWARE:[ \t]*([^\n]*)\n)?"
    r"(?:EFFECTIVE_DATE:[ \t]*([^\n]*)\n)?"
    r"(?:SUPERSEDES:[ \t]*([^\n]*)\n)?"
    r"---\n",
)


def parse_supersedes(value: Optional[str]) -> list[str]:
    """Split a SUPERSEDES header value into a list of source URLs.

    Accepts comma- or whitespace-separated URLs; dedupes preserving order.
    """
    if not value:
        return []
    parts = re.split(r"[,\s]+", value.strip())
    seen: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in seen:
            seen.append(p)
    return seen


def year_to_effective_date(year: Any) -> Optional[str]:
    """Derive an ISO ``effective_date`` from a seed row's ``year`` (or date).

    ``"2024"`` -> ``"2024-01-01"``; a full ISO date is passed through; anything
    unparseable (or empty) -> ``None``.
    """
    if year is None:
        return None
    s = str(year).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s).isoformat()  # already a full ISO date
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return f"{m.group(1)}-01-01"
    return None


def most_recent_effective_date(years: Iterable[Any]) -> Optional[str]:
    """Most recent ``effective_date`` derivable from a set of years/dates.

    Used to stamp a grouped raw file (one header for many seed rows) with the
    newest vintage present. ISO date strings sort chronologically.
    """
    dates = [d for d in (year_to_effective_date(y) for y in years) if d]
    return max(dates) if dates else None


def parse_header(raw: str) -> tuple[dict[str, Any], str]:
    """Parse a raw-file metadata header; return (meta, body).

    Raises ValueError if the required header block is missing.
    """
    m = HEADER_RE.match(raw)
    if not m:
        raise ValueError("Missing metadata header in file")
    meta: dict[str, Any] = {
        "source_title": m.group(1).strip(),
        "source_url": m.group(2).strip(),
        "ministry": m.group(3).strip(),
        "domain": m.group(4).strip(),
        "source_date": (m.group(5) or "").strip() or None,
        "expiry_aware": (m.group(6) or "").strip().lower() == "true",
        "effective_date": (m.group(7) or "").strip() or None,
        "supersedes": parse_supersedes(m.group(8)),
    }
    body = raw[m.end():]
    return meta, body


# --- content-level effective-date extraction -------------------------------
# Bahasa Malaysia + English month names (incl. common abbreviations).
_MONTHS: dict[str, int] = {
    "january": 1, "jan": 1, "januari": 1,
    "february": 2, "feb": 2, "februari": 2,
    "march": 3, "mar": 3, "mac": 3,
    "april": 4, "apr": 4,
    "may": 5, "mei": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7, "julai": 7,
    "august": 8, "aug": 8, "ogos": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "oktober": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12, "disember": 12,
}

# Phrases that introduce an explicit commencement date (BM + EN).
_EFFECTIVE_TRIGGER_RE = re.compile(
    r"(?:mula\s+)?berkuat\s+kuasa(?:\s+(?:pada|mulai|dari))?"
    r"|effective(?:\s+(?:from|on))?"
    r"|with\s+effect\s+from"
    r"|w\.?\s*e\.?\s*f\.?",
    re.IGNORECASE,
)
# "Budget 2024" / "Bajet 2024" → the fiscal year the figure belongs to.
_BUDGET_YEAR_RE = re.compile(r"\b(?:Bajet|Budget)\s+(\d{4})\b", re.IGNORECASE)

_DMY_NUMERIC_RE = re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})")
_DMY_TEXT_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
_MY_TEXT_RE = re.compile(r"([A-Za-z]+)\s+(\d{4})")


def _iso_or_none(year: int, month: int, day: int) -> Optional[str]:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _parse_date_fragment(fragment: str) -> Optional[str]:
    """Parse the first date out of a short text fragment.

    Handles Malaysian ``dd/mm/yyyy``, ``D Month YYYY``, and ``Month YYYY``
    (day defaults to the 1st). Returns an ISO date string or None.
    """
    m = _DMY_NUMERIC_RE.search(fragment)
    if m:  # Malaysian day-first numeric date
        return _iso_or_none(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = _DMY_TEXT_RE.search(fragment)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        if month:
            iso = _iso_or_none(int(m.group(3)), month, int(m.group(1)))
            if iso:
                return iso
    m = _MY_TEXT_RE.search(fragment)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            return _iso_or_none(int(m.group(2)), month, 1)
    return None


def extract_effective_date(text: str) -> Optional[str]:
    """Extract an ISO ``effective_date`` from a chunk's text, or None.

    Precedence:
      1. An explicit commencement phrase (``berkuat kuasa`` / ``effective`` /
         ``w.e.f.``) followed by a date — the most precise signal.
      2. A ``Budget``/``Bajet YYYY`` reference → 1 Jan of that fiscal year.

    Chunk-level extraction is more precise than a file-level year, so callers
    should prefer this over the header default and fall back to it.
    """
    if not text:
        return None
    for trigger in _EFFECTIVE_TRIGGER_RE.finditer(text):
        # Look just past the trigger phrase for the date it introduces.
        fragment = text[trigger.end(): trigger.end() + 40]
        parsed = _parse_date_fragment(fragment)
        if parsed:
            return parsed
    m = _BUDGET_YEAR_RE.search(text)
    if m:
        return f"{m.group(1)}-01-01"
    return None


def build_supersession_map(chunks: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Map each superseded source_url -> a representative new chunk id.

    Built from chunk records that declare ``supersedes`` (a list of old source
    URLs). The old chunks matching those URLs are hard-rejected at query time,
    so the target id only needs to be a valid, freshly-ingested chunk from the
    document that declared the supersession.
    """
    mapping: dict[str, str] = {}
    for chunk in chunks:
        for old_url in chunk.get("supersedes") or []:
            if old_url and old_url not in mapping and chunk.get("id"):
                mapping[old_url] = chunk["id"]
    return mapping
