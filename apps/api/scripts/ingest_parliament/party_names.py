"""Canonical party names for mp_profiles.party.

The MP roster is scraped from per-MP profile pages that write the party in
whatever form that page's author chose, so one party arrives as many strings
("PAS", "Parti Islam Se-Malaysia", "PARTI ISLAM SE-MALAYSIA (PAS)", ...). The
read path searches the column with ILIKE, so unnormalised values make "Bersatu"
miss every MP stored as "PPBM", and any per-party count come out wrong.

normalise_party() maps the known spellings to one short canonical name. It only
ever recognises a spelling it has been told about: an unfamiliar value is
returned unchanged (never guessed at, never dropped), and unrecognised() lets
the loader report it so a person can decide. Coalition labels such as
"Barisan Nasional" or "GRS" are deliberately NOT mapped to a party: a coalition
says nothing about which member party the MP belongs to.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Optional

# canonical name -> every other spelling seen (compared case-insensitively).
# The canonical name itself is always accepted.
_ALIASES: dict[str, tuple[str, ...]] = {
    "PAS": ("Parti Islam Se-Malaysia", "Malaysia Islamic Party", "Malaysian Islamic Party"),
    "DAP": ("Democratic Action Party",),
    "UMNO": ("United Malays National Organisation", "United Malays National Organization"),
    "PKR": ("Parti Keadilan Rakyat", "People's Justice Party"),
    # PPBM is Bersatu's former abbreviation; the codebase uses BERSATU.
    "BERSATU": (
        "PPBM",
        "Parti Pribumi Bersatu Malaysia",
        "Malaysian United Indigenous Party",
        "Malaysian United Indigenous Party / Parti Pribumi Bersatu Malaysia",
    ),
    "AMANAH": ("Parti Amanah Negara", "National Trust Party"),
    # PPB is an alternate abbreviation of the same party.
    "PBB": ("PPB", "Parti Pesaka Bumiputera Bersatu"),
    "PRS": ("Parti Rakyat Sarawak",),
    "SUPP": ("Sarawak United Peoples' Party", "Sarawak United Peoples Party"),
    "PDP": ("Progressive Democratic Party",),
    "WARISAN": ("Parti Warisan Sabah",),
    "KDM": ("Parti Kesejahteraan Demokratik Masyarakat", "Kesejahteraan Demokratik Masyarakat"),
    "PBDS": ("Parti Bansa Dayak Sarawak",),
    "PBS": ("Parti Bersatu Sabah",),
    "MUDA": ("Malaysian United Democratic Alliance",),
    "UPKO": ("United Pasokmomogun Kadazandusun Murut Organisation",),
    "MCA": ("Malaysian Chinese Association",),
    "MIC": ("Malaysian Indian Congress",),
    "STAR": ("Parti Solidariti Tanah Airku", "State Reform Party"),
    "PBRS": ("Parti Bersatu Rakyat Sabah",),
    "Independent": ("Bebas",),
}

CANONICAL: frozenset[str] = frozenset(_ALIASES)

_LOOKUP: dict[str, str] = {}
for _canonical, _aliases in _ALIASES.items():
    for _name in (_canonical, *_aliases):
        _LOOKUP[_name.casefold()] = _canonical

# "Democratic Action Party (DAP)" -> the trailing bracket names the party.
_TRAILING_PAREN_RE = re.compile(r"\(([^()]+)\)\s*$")


def normalise_party(raw: Optional[str]) -> Optional[str]:
    """Canonical party name, None for blank, or the cleaned input if unknown."""
    if raw is None:
        return None
    text = " ".join(str(raw).split())
    if not text:
        return None
    hit = _LOOKUP.get(text.casefold())
    if hit:
        return hit
    bracketed = _TRAILING_PAREN_RE.search(text)
    if bracketed:
        hit = _LOOKUP.get(bracketed.group(1).strip().casefold())
        if hit:
            return hit
    return text


def unrecognised(parties: Iterable[Optional[str]]) -> Counter[str]:
    """Normalised party values that are not canonical (excluding blanks)."""
    return Counter(p for p in parties if p and p not in CANONICAL)
