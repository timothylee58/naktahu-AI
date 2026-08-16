"""Unit tests for the pure, network-free parts of scraper.py.

_parse_listing_page/scrape_all require a live site and are NOT covered
here — see scraper.py's module docstring on why those selectors are
unverified placeholders.
"""
from __future__ import annotations

from .scraper import parse_scope


def test_parse_scope_state_prefix() -> None:
    assert parse_scope("Selangor: Skim Rawatan Jantung") == "state:selangor"


def test_parse_scope_case_insensitive() -> None:
    assert parse_scope("kuala lumpur: Bantuan Sewa") == "state:kuala-lumpur"


def test_parse_scope_no_prefix_defaults_federal() -> None:
    assert parse_scope("Bantuan Sara Hidup") == "federal"


def test_parse_scope_colon_without_state_defaults_federal() -> None:
    assert parse_scope("Program: Bantuan Am") == "federal"


def test_parse_scope_alias_penang() -> None:
    assert parse_scope("Penang: Skim X") == "state:pulau-pinang"


def test_parse_scope_alias_melaka_english() -> None:
    assert parse_scope("Malacca: Skim Y") == "state:melaka"
