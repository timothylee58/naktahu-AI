"""Hand-checked party values for MPs whose scraped party is missing or is only
a coalition label.

The roster scrape leaves 6 MPs with no party and gives 2 more only a coalition
("GRS", "Barisan Nasional"). Someone checked these against an official source
and recorded the answer here. The values below are applied as written.

An override is tied to the MP it was checked for, not just the seat. If a
by-election or the roster later puts a different person in the seat, the
override would silently give the new MP the old MP's party, so it is skipped
(and logged) whenever the scraped name no longer matches the name recorded in
_CHECKED_FOR. After a seat changes hands, check the new MP and update both
tables.
"""
from __future__ import annotations

import re
from typing import Optional

import structlog

log = structlog.get_logger(__name__)

MANUAL_PARTY_OVERRIDES = {
    "P001": "PAS",
    "P019": "PAS",
    "P132": "PKR",
    "P156": "UMNO",
    "P175": "GRS",
    "P179": "GRS",
    "P178": "GRS",
    "P184": "Barisan Nasional",
}

# The MP in each seat, as named in the scraped roster, when the override above
# was checked. Every code in MANUAL_PARTY_OVERRIDES must appear here.
_CHECKED_FOR = {
    "P001": "Rushdan Bin Rusmi",
    "P019": "Mumtaz Binti Md. Nawi",
    "P132": "Aminuddin Bin Harun",
    "P156": "Mohamed Khaled Nordin",
    "P175": "Armizan Mohd Ali",
    "P179": "Jonathan Bin Yasin",
    "P178": "Matbali Musah",
    "P184": "Suhaimi Bin Nasir",
}


def canonical_seat_code(code: str) -> str:
    """'P.001', 'p001', ' P 001 ' -> 'P001'.

    Scrapers disagree on whether a seat code carries a period, and the postcode
    crosswalk (seed_postcode_seats.normalise_code) and the rows already in
    mp_profiles use the undotted form. Comparing or storing the raw code lets a
    dotted one silently miss an override, or create a second row for a seat
    that already exists.
    """
    return re.sub(r"[\s.]", "", code or "").upper()


def _same_person(a: str, b: str) -> bool:
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def apply_party_override(
    constituency_code: str, full_name: str, scraped_party: Optional[str]
) -> Optional[str]:
    """The override for this seat if it applies to this MP, else scraped_party."""
    constituency_code = canonical_seat_code(constituency_code)
    override = MANUAL_PARTY_OVERRIDES.get(constituency_code)
    if override is None:
        return scraped_party
    checked_for = _CHECKED_FOR.get(constituency_code)
    if checked_for is None or not _same_person(full_name, checked_for):
        log.warning(
            "mp_party_override_skipped_mp_changed",
            constituency_code=constituency_code,
            roster_name=full_name,
            checked_for=checked_for,
        )
        return scraped_party
    return override
