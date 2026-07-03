"""Tests for the dep-free ingestion freshness-metadata helpers.

Run with: ``PYTHONPATH=. pytest scripts/ingest/test_metadata.py -q``.
"""
from __future__ import annotations

import pytest

from scripts.ingest.metadata import (
    build_supersession_map,
    most_recent_effective_date,
    parse_header,
    parse_supersedes,
    year_to_effective_date,
)


# --- year_to_effective_date -----------------------------------------------


def test_year_to_effective_date_from_year() -> None:
    assert year_to_effective_date("2024") == "2024-01-01"
    assert year_to_effective_date(2024) == "2024-01-01"


def test_year_to_effective_date_passthrough_iso() -> None:
    assert year_to_effective_date("2024-05-01") == "2024-05-01"


def test_year_to_effective_date_invalid_or_empty() -> None:
    assert year_to_effective_date("") is None
    assert year_to_effective_date(None) is None
    assert year_to_effective_date("not-a-year") is None
    assert year_to_effective_date("24") is None  # not 4 digits


def test_most_recent_effective_date() -> None:
    assert most_recent_effective_date(["2022", "2024", "2023"]) == "2024-01-01"
    assert most_recent_effective_date(["2023", "2024-06-01"]) == "2024-06-01"
    assert most_recent_effective_date([]) is None
    assert most_recent_effective_date(["", "nope"]) is None


# --- parse_supersedes ------------------------------------------------------


def test_parse_supersedes_variants() -> None:
    assert parse_supersedes("https://a.gov.my, https://b.gov.my") == [
        "https://a.gov.my",
        "https://b.gov.my",
    ]
    assert parse_supersedes("https://a.gov.my https://b.gov.my") == [
        "https://a.gov.my",
        "https://b.gov.my",
    ]
    assert parse_supersedes("https://a.gov.my, https://a.gov.my") == ["https://a.gov.my"]
    assert parse_supersedes("") == []
    assert parse_supersedes(None) == []


# --- parse_header ----------------------------------------------------------

_FULL_HEADER = (
    "SOURCE_TITLE: EPF Withdrawal 2024\n"
    "SOURCE_URL: https://www.kwsp.gov.my/2024\n"
    "MINISTRY: KWSP\n"
    "DOMAIN: epf\n"
    "SOURCE_DATE: 2024-05-01\n"
    "EXPIRY_AWARE: true\n"
    "EFFECTIVE_DATE: 2024-05-01\n"
    "SUPERSEDES: https://www.kwsp.gov.my/2023\n"
    "---\n"
    "Body content about EPF withdrawal.\n"
)

_MINIMAL_HEADER = (
    "SOURCE_TITLE: Evergreen Guide\n"
    "SOURCE_URL: https://www.ssm.gov.my\n"
    "MINISTRY: SSM\n"
    "DOMAIN: business\n"
    "---\n"
    "How to register a company.\n"
)


def test_parse_header_full() -> None:
    meta, body = parse_header(_FULL_HEADER)
    assert meta["domain"] == "epf"
    assert meta["effective_date"] == "2024-05-01"
    assert meta["expiry_aware"] is True
    assert meta["supersedes"] == ["https://www.kwsp.gov.my/2023"]
    assert body.startswith("Body content")


def test_parse_header_minimal_defaults() -> None:
    meta, body = parse_header(_MINIMAL_HEADER)
    assert meta["effective_date"] is None
    assert meta["supersedes"] == []
    assert meta["expiry_aware"] is False
    assert body.startswith("How to register")


def test_parse_header_missing_raises() -> None:
    with pytest.raises(ValueError):
        parse_header("no header here\njust text\n")


# --- build_supersession_map ------------------------------------------------


def test_build_supersession_map() -> None:
    chunks = [
        {"id": "new-1", "supersedes": ["https://old-a", "https://old-b"]},
        {"id": "new-2", "supersedes": ["https://old-a"]},  # first id wins
        {"id": "new-3", "supersedes": []},
        {"id": "new-4"},  # no supersedes key
    ]
    assert build_supersession_map(chunks) == {
        "https://old-a": "new-1",
        "https://old-b": "new-1",
    }


def test_build_supersession_map_empty() -> None:
    assert build_supersession_map([{"id": "x"}]) == {}
