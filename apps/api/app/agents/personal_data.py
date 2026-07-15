"""Detect personal-data queries (e.g. "what's my EPF balance") that NakTahu
cannot answer — it has no access to any user's case-specific records — and
surface the matching agency's real contact channel instead of a generic
refusal. Curated directory, not RAG: these are stable government contact
points, not something to source from document_chunks.

First-pass coverage: EPF/KWSP, LHDN (tax), JPN (IC/birth/death/citizenship) —
the three domains covered by CLAUDE.md's non-strict/strict staleness split
that also generate the highest volume of personal-record queries.
"""
from __future__ import annotations

import re
from typing import Optional, TypedDict


class AgencyContact(TypedDict):
    agency: str
    domain: str
    hotline: str
    portal: str


_AGENCY_DIRECTORY: dict[str, AgencyContact] = {
    "epf": {
        "agency": "KWSP / EPF",
        "domain": "epf",
        "hotline": "03-8922 6000",
        "portal": "https://www.kwsp.gov.my",
    },
    "tax": {
        "agency": "LHDN",
        "domain": "tax",
        "hotline": "03-8911 1000",
        "portal": "https://www.hasil.gov.my",
    },
    "jpn": {
        "agency": "JPN (Jabatan Pendaftaran Negara)",
        "domain": "government",
        "hotline": "03-8880 6555",
        "portal": "https://www.jpn.gov.my",
    },
}

# Personal-record pronoun/possessive markers — "my/I have" balance, status,
# refund, etc. — as opposed to a general question about the rules themselves
# ("what is the EPF withdrawal age" should NOT trigger this).
_PERSONAL_MARKER_RE = re.compile(
    r"\b(my|i've|i have|i am|i'm|check my|status of my)\b"
    r"|(saya|akaun saya|baki saya|status saya)",
    re.IGNORECASE,
)

_DOMAIN_KEYWORDS: dict[str, re.Pattern[str]] = {
    "epf": re.compile(r"\b(epf|kwsp)\b", re.IGNORECASE),
    "tax": re.compile(r"\b(tax refund|lhdn|income tax|cukai pendapatan|bayaran balik cukai)\b", re.IGNORECASE),
    "jpn": re.compile(r"\b(ic|mykad|birth cert|death cert|sijil lahir|sijil kematian|kad pengenalan)\b", re.IGNORECASE),
}


def detect_personal_data_agency(query: str, domain: Optional[str]) -> Optional[AgencyContact]:
    """Return the matching agency contact if ``query`` is asking about the
    user's own case-specific record, else ``None``.

    Both a personal marker AND a domain-keyword hit are required — a bare
    "my" isn't enough (too broad), and a bare "EPF" isn't enough (routine
    rules questions about EPF are exactly what RAG should answer).
    """
    if not query or not _PERSONAL_MARKER_RE.search(query):
        return None

    for key, pattern in _DOMAIN_KEYWORDS.items():
        if pattern.search(query):
            return _AGENCY_DIRECTORY[key]

    # Fall back to the router's domain classification only when it's one we
    # have a directory entry for — avoids guessing an agency from a vague
    # personal query with no domain-specific keyword at all.
    if domain in _AGENCY_DIRECTORY:
        return _AGENCY_DIRECTORY[domain]

    return None
