"""Extract a rule's validity window from ingested government text.

Feeds document_chunks.effective_date / effective_until (migration 052), which
analyst_node uses to keep announced-but-not-yet-effective rules out of
today's answer and to drop rules whose window has closed.

Deliberately conservative. A wrong date is worse than no date: no date leaves
a chunk with today's behaviour, while a wrong one can hide the current rule.
So only explicit phrases count ("berkuat kuasa pada 1 Januari 2027",
"effective from 1 January 2027", "sehingga 31 Disember 2026"), and when a
chunk states two different start (or end) dates we return None for that side
rather than guess which one the chunk is about.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Optional

_MONTHS = {
    "januari": 1, "january": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "mac": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "jun": 6, "june": 6,
    "julai": 7, "july": 7, "jul": 7,
    "ogos": 8, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "disember": 12, "december": 12, "dis": 12, "dec": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE = rf"(\d{{1,2}})\s+({_MONTH_ALT})\.?\s+(\d{{4}})"

_START_RE = re.compile(
    r"(?:berkuat\s*kuasa|berkuatkuasa|mulai|bermula|effective|with\s+effect\s+from|"
    r"w\.?e\.?f\.?|commencing|starting)"
    r"(?:\s+(?:pada|on|from|dari|daripada))?\s+" + _DATE,
    re.IGNORECASE,
)
_UNTIL_RE = re.compile(
    r"(?:sehingga|hingga|until|till|up\s+to|berakhir\s+pada|tamat\s+pada|expires?\s+on|"
    r"valid\s+until|sah\s+sehingga)\s+" + _DATE,
    re.IGNORECASE,
)
_RANGE_RE = re.compile(
    rf"(?:dari|daripada|from)\s+{_DATE}\s+(?:hingga|sehingga|to|until|-|–)\s+{_DATE}",
    re.IGNORECASE,
)
_YA_RE = re.compile(r"(?:tahun\s+taksiran|year\s+of\s+assessment|\bYA)\s*(\d{4})", re.IGNORECASE)
# "mulai Tahun Taksiran 2027" / "with effect from YA 2027" starts a rule that
# keeps applying, unlike "for YA 2027", which is a one-year window. Budget
# speeches use the open-ended form constantly; treating it as a one-year
# window would make the rule look expired after 31 December of that year.
_YA_START_RE = re.compile(
    r"(?:berkuat\s*kuasa|berkuatkuasa|mulai|bermula|effective|with\s+effect\s+from|commencing|starting|from|dari|daripada)"
    r"(?:\s+(?:pada|on))?\s+(?:tahun\s+taksiran|year\s+of\s+assessment|\bYA)\s*(\d{4})",
    re.IGNORECASE,
)
_ONWARDS_RE = re.compile(r"dan\s+seterusnya|seterusnya|and\s+(?:subsequent|following)\s+years?|onwards?", re.IGNORECASE)


@dataclass(frozen=True)
class ValidityWindow:
    effective_date: Optional[date] = None
    effective_until: Optional[date] = None


def _to_date(day: str, month: str, year: str) -> Optional[date]:
    try:
        return date(int(year), _MONTHS[month.lower()], int(day))
    except (KeyError, ValueError):
        return None


def _single(dates: set[date]) -> Optional[date]:
    """The date if exactly one distinct value was found, else None (ambiguous)."""
    return next(iter(dates)) if len(dates) == 1 else None


def extract_validity_window(text: str) -> ValidityWindow:
    starts: set[date] = set()
    untils: set[date] = set()

    for m in _RANGE_RE.finditer(text):
        start, end = _to_date(*m.group(1, 2, 3)), _to_date(*m.group(4, 5, 6))
        if start:
            starts.add(start)
        if end:
            untils.add(end)
    for m in _START_RE.finditer(text):
        if d := _to_date(*m.groups()):
            starts.add(d)
    for m in _UNTIL_RE.finditer(text):
        if d := _to_date(*m.groups()):
            untils.add(d)

    for m in _YA_START_RE.finditer(text):
        starts.add(date(int(m.group(1)), 1, 1))

    start, until = _single(starts), _single(untils)

    # Year of Assessment N covers income year N. Used only when the text gives
    # no explicit dates, and only when it names a single YA. "YA N and onwards"
    # is a start, not a window.
    if not starts and not untils:
        years = {int(y) for y in _YA_RE.findall(text)}
        if len(years) == 1:
            year = years.pop()
            start = date(year, 1, 1)
            until = None if _ONWARDS_RE.search(text) else date(year, 12, 31)

    if start and until and until < start:
        # Contradictory; matches the CHECK constraint in migration 052.
        return ValidityWindow()
    return ValidityWindow(start, until)


def parse_published(value: str) -> Optional[date]:
    """RSS pubDate (RFC 822) or Atom published/updated (ISO 8601) -> date."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
