"""Unit tests for app.services.malay_morph (Malay affix query expansion)."""
from __future__ import annotations

import re

import pytest

from app.services.malay_morph import build_keyword_tsquery, candidate_roots, expand_token


@pytest.mark.parametrize(
    ("word", "related"),
    [
        ("memohon", "permohonan"),
        ("permohonan", "memohon"),
        ("pemohon", "permohonan"),
        ("mendaftar", "pendaftaran"),
        ("pendaftaran", "daftar"),
        ("menulis", "tulisan"),
        ("pembayaran", "membayar"),
        ("pengiraan", "mengira"),
        ("menyimpan", "simpanan"),
        ("diluluskan", "kelulusan"),
        ("cukai", "percukaian"),
    ],
)
def test_expansion_links_affixed_forms(word: str, related: str) -> None:
    assert related in expand_token(word)


def test_nasal_roots_are_restored() -> None:
    assert "tulis" in candidate_roots("menulis")
    assert "kira" in candidate_roots("mengira")
    assert "simpan" in candidate_roots("menyimpan")


def test_short_roots_are_not_generated() -> None:
    # "berapa" -> "apa" would OR-in one of the most common words
    assert "apa" not in candidate_roots("berapa")


def test_tsquery_shape_is_and_of_or_groups() -> None:
    tsq = build_keyword_tsquery("Cara memohon PTPTN?")
    assert tsq is not None
    groups = tsq.split(" & ")
    assert len(groups) == 3
    assert all(g.startswith("(") and g.endswith(")") for g in groups)
    assert "permohonan" in groups[1]


def test_tsquery_cannot_carry_operators_from_input() -> None:
    tsq = build_keyword_tsquery("cukai' | !(x) & <-> :* \\ ;drop")
    assert tsq is not None
    # only lowercase alphanumerics, our own operators, spaces and parens
    assert re.fullmatch(r"[a-z0-9 ()|&]+", tsq)


def test_non_latin_query_returns_none() -> None:
    assert build_keyword_tsquery("如何申请学贷") is None
    assert build_keyword_tsquery("   ") is None


def test_query_size_is_bounded() -> None:
    long_query = " ".join(f"perkataan{i}" for i in range(50))
    tsq = build_keyword_tsquery(long_query)
    assert tsq is not None
    groups = tsq.split(" & ")
    assert len(groups) <= 8
    assert all(len(g.split(" | ")) <= 64 for g in groups)
