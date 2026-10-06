"""Tests for scripts.ingest_parliament.party_names.

The fixture is the real distribution of `party` strings from the scraped
222-MP roster (mymp.org.my), which is what made normalisation necessary: one
party appeared under up to five spellings.
"""
from __future__ import annotations

from collections import Counter

import pytest

from scripts.ingest_parliament.party_names import CANONICAL, normalise_party, unrecognised

_SCRAPED_PARTY_COUNTS = {
    "PAS": 34, "DAP": 33, "UMNO": 25, "PKR": 18, "PPBM": 14, "BERSATU": 11, "AMANAH": 7, "PBB": 6,
    "Parti Pesaka Bumiputera Bersatu (PBB)": 6, "Democratic Action Party (DAP)": 5,
    "Parti Keadilan Rakyat (PKR)": 5, "People's Justice Party (PKR)": 4,
    "Parti Pesaka Bumiputera Bersatu": 4, "Parti Keadilan Rakyat": 3, "Parti Islam Se-Malaysia": 3,
    "Parti Pribumi Bersatu Malaysia": 3, "Democratic Action Party": 2,
    "Parti Islam Se-Malaysia (PAS)": 2, "MCA": 2, "WARISAN": 2, "UPKO": 2, "Parti Rakyat Sarawak": 2,
    "Malaysian United Indigenous Party / Parti Pribumi Bersatu Malaysia (BERSATU)": 1,
    "Malaysia Islamic Party (PAS)": 1, "Malaysian United Indigenous Party (BERSATU)": 1,
    "PARTI ISLAM SE-MALAYSIA (PAS)": 1, "MIC": 1, "Malaysian United Democratic Alliance (MUDA)": 1,
    "Parti Amanah Negara": 1, "Independent": 1, "Parti Kesejahteraan Demokratik Masyarakat": 1,
    "GRS": 1, "STAR": 1, "Kesejahteraan Demokratik Masyarakat": 1, "PBRS": 1, "Barisan Nasional": 1,
    "Parti Warisan Sabah": 1, "Parti Bersatu Sabah": 1, "SUPP": 1, "Sarawak United Peoples' Party": 1,
    "Parti Bansa Dayak Sarawak": 1, "Parti Rakyat Sarawak (PRS)": 1,
    "Progressive Democratic Party (PDP)": 1, "Parti Pesaka Bumiputera Bersatu (PPB)": 1, "PDP": 1,
}


def _normalised_totals() -> Counter[str]:
    totals: Counter[str] = Counter()
    for raw, n in _SCRAPED_PARTY_COUNTS.items():
        totals[normalise_party(raw)] += n
    return totals


def test_real_roster_collapses_to_one_name_per_party():
    totals = _normalised_totals()
    assert totals["PAS"] == 41
    assert totals["DAP"] == 40
    assert totals["PKR"] == 30
    assert totals["BERSATU"] == 30  # PPBM + BERSATU + two long forms
    assert totals["PBB"] == 17
    assert totals["UMNO"] == 25
    assert totals["AMANAH"] == 8
    assert totals["WARISAN"] == 3
    assert totals["PRS"] == 3
    assert totals["PDP"] == 2 and totals["SUPP"] == 2 and totals["KDM"] == 2
    assert "PPBM" not in totals


def test_only_coalition_labels_are_left_unrecognised():
    """Nothing is guessed: coalition labels stay as written for a person to decide."""
    left = unrecognised(normalise_party(raw) for raw in _SCRAPED_PARTY_COUNTS)
    assert set(left) == {"GRS", "Barisan Nasional"}


def test_every_canonical_name_is_stable():
    for name in CANONICAL:
        assert normalise_party(name) == name


@pytest.mark.parametrize("blank", [None, "", "   ", "\n"])
def test_blank_is_none(blank):
    assert normalise_party(blank) is None


def test_unknown_value_is_kept_not_dropped_or_guessed():
    assert normalise_party("  Parti   Baru  Entah ") == "Parti Baru Entah"
    assert normalise_party("PH") == "PH"  # a coalition, not a party


def test_case_and_whitespace_insensitive():
    assert normalise_party("  parti   islam  se-malaysia ") == "PAS"
    assert normalise_party("ppbm") == "BERSATU"
