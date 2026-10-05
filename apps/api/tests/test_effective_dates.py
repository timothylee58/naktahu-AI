"""Tests for scripts.effective_dates (validity-window extraction at ingestion)."""
from __future__ import annotations

from datetime import date

import pytest

from scripts.effective_dates import ValidityWindow, extract_validity_window, parse_published


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pelepasan dinaikkan kepada RM3,000 berkuat kuasa pada 1 Januari 2027.",
         ValidityWindow(date(2027, 1, 1), None)),
        ("The new rate is effective from 1 March 2026 until 31 December 2026.",
         ValidityWindow(date(2026, 3, 1), date(2026, 12, 31))),
        ("Kadar ini sah sehingga 31 Disember 2026.", ValidityWindow(None, date(2026, 12, 31))),
        ("Insentif ini dari 1 Jun 2026 hingga 30 November 2026.",
         ValidityWindow(date(2026, 6, 1), date(2026, 11, 30))),
        ("Mulai 1 Julai 2026, caruman minimum ialah 2%.", ValidityWindow(date(2026, 7, 1), None)),
        ("With effect from 15 Oct 2026 applications open online.", ValidityWindow(date(2026, 10, 15), None)),
        ("Pelepasan untuk Tahun Taksiran 2026 ialah RM2,500.",
         ValidityWindow(date(2026, 1, 1), date(2026, 12, 31))),
    ],
)
def test_explicit_validity_phrases(text: str, expected: ValidityWindow) -> None:
    assert extract_validity_window(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "No dates in this paragraph at all.",
        # Two different start dates: ambiguous, so leave it to a human.
        "Effective 1 January 2026 for employers and effective 1 July 2026 for employees.",
        # Two Years of Assessment: comparison text, not a rule window.
        "Compare the YA2025 and YA 2026 reliefs.",
        # A bare date with no validity keyword is not an effective date.
        "The Budget was tabled on 10 October 2026.",
        # Impossible calendar date.
        "Berkuat kuasa pada 31 Februari 2027.",
    ],
)
def test_ambiguous_or_missing_dates_return_nothing(text: str) -> None:
    window = extract_validity_window(text)
    assert window.effective_date is None


def test_contradictory_window_is_dropped() -> None:
    assert extract_validity_window("Effective 1 March 2027, valid until 31 December 2026.") == ValidityWindow()


def test_explicit_dates_win_over_year_of_assessment() -> None:
    window = extract_validity_window("For YA 2026, berkuat kuasa pada 1 Julai 2026.")
    assert window == ValidityWindow(date(2026, 7, 1), None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Tue, 10 Nov 2026 08:00:00 +0800", date(2026, 11, 10)),
        ("2026-11-10T08:00:00Z", date(2026, 11, 10)),
        ("2026-11-10", date(2026, 11, 10)),
        ("", None),
        ("not a date", None),
    ],
)
def test_parse_published(value: str, expected: date | None) -> None:
    assert parse_published(value) == expected
