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
