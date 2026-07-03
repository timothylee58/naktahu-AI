"""Tests for the custom temporal_accuracy metric.

Uses an injected ``today`` so scores are deterministic regardless of when the
suite runs. Run with: ``pytest scripts/evals/ -q``.
"""
from __future__ import annotations

from datetime import date, timedelta

from scripts.evals.temporal_scorer import (
    TEMPORAL_ACCURACY_GATE,
    aggregate_temporal_accuracy,
    score_temporal_accuracy,
    temporal_accuracy,
)

_TODAY = date(2026, 7, 3)


def _ago(days: int) -> date:
    return _TODAY - timedelta(days=days)


# --- single-chunk scoring -------------------------------------------------


def test_superseded_chunk_hard_fails() -> None:
    # Even with a brand-new effective_date, a superseded chunk scores 0.0.
    assert score_temporal_accuracy(_TODAY, "newer-chunk-id", "epf", today=_TODAY) == 0.0


def test_missing_effective_date_is_moderately_risky() -> None:
    assert score_temporal_accuracy(None, None, "tax", today=_TODAY) == 0.5


def test_recent_chunk_is_fully_current() -> None:
    assert score_temporal_accuracy(_ago(30), None, "epf", today=_TODAY) == 1.0


def test_future_effective_date_is_current() -> None:
    assert score_temporal_accuracy(_TODAY + timedelta(days=30), None, "epf", today=_TODAY) == 1.0


def test_strict_domain_has_tighter_window_than_lenient() -> None:
    # 250 days old: within the 365-day lenient window (education → 1.0) but
    # past the 180-day strict window (epf → 0.6).
    aged = _ago(250)
    assert score_temporal_accuracy(aged, None, "education", today=_TODAY) == 1.0
    assert score_temporal_accuracy(aged, None, "epf", today=_TODAY) == 0.6


def test_within_two_windows_scores_partial() -> None:
    # epf strict threshold 180; 300 days is within 2x (360) → 0.6.
    assert score_temporal_accuracy(_ago(300), None, "epf", today=_TODAY) == 0.6


def test_very_old_chunk_decays_and_is_floored() -> None:
    # epf threshold 180; 400 days > 2x(360) → decay 1 - 400/720 ≈ 0.444.
    score = score_temporal_accuracy(_ago(400), None, "epf", today=_TODAY)
    assert 0.44 <= score <= 0.45
    # Extremely old → floored at 0.1.
    assert score_temporal_accuracy(_ago(10_000), None, "epf", today=_TODAY) == 0.1


def test_iso_string_dates_are_accepted() -> None:
    assert score_temporal_accuracy(_ago(30).isoformat(), None, "epf", today=_TODAY) == 1.0
    # Unparseable string → treated as missing metadata.
    assert score_temporal_accuracy("not-a-date", None, "epf", today=_TODAY) == 0.5


# --- aggregation (per-answer sample) --------------------------------------


def test_aggregate_is_worst_case_over_chunks() -> None:
    fresh = {"effective_date": _ago(10)}
    stale = {"effective_date": _ago(1000)}
    # min over chunks: one stale source taints the answer.
    assert aggregate_temporal_accuracy([fresh, stale], domain="epf", today=_TODAY) < 1.0
    assert aggregate_temporal_accuracy([fresh, fresh], domain="epf", today=_TODAY) == 1.0


def test_aggregate_empty_is_unknown() -> None:
    assert aggregate_temporal_accuracy([], domain="epf", today=_TODAY) == 0.5


def test_aggregate_reads_object_attributes() -> None:
    class _Chunk:
        def __init__(self, effective_date, superseded_by=None):
            self.effective_date = effective_date
            self.superseded_by = superseded_by

    chunks = [_Chunk(_ago(10)), _Chunk(_ago(10), superseded_by="x")]
    # The superseded chunk drops the aggregate to 0.0.
    assert aggregate_temporal_accuracy(chunks, domain="epf", today=_TODAY) == 0.0


# --- gate: the EPF RM1,000 / RM500 scenario -------------------------------


def test_gate_catches_stale_but_faithful_epf_answer() -> None:
    """The exact failure RAGAS faithfulness misses: last year's EPF cap is the
    only retrieved source. Faithfulness would be 1.0; temporal_accuracy must
    fall below the gate so the eval fails instead of passing silently."""
    sample = {
        "domain": "epf",
        "retrieved_chunks": [
            {"effective_date": date(2023, 10, 1), "superseded_by": None},  # RM1,000
        ],
    }
    score = temporal_accuracy.score(sample, today=_TODAY)
    assert score < TEMPORAL_ACCURACY_GATE
    assert temporal_accuracy.passes(sample, today=_TODAY) is False


def test_gate_rejects_superseded_epf_chunk() -> None:
    sample = {
        "domain": "epf",
        "retrieved_chunks": [
            {"effective_date": date(2023, 10, 1), "superseded_by": "epf-2024"},
        ],
    }
    assert temporal_accuracy.score(sample, today=_TODAY) == 0.0
    assert temporal_accuracy.passes(sample, today=_TODAY) is False


def test_gate_passes_for_current_epf_answer() -> None:
    sample = {
        "domain": "epf",
        "retrieved_chunks": [
            {"effective_date": _ago(30), "superseded_by": None},  # RM500, current
        ],
    }
    assert temporal_accuracy.score(sample, today=_TODAY) == 1.0
    assert temporal_accuracy.passes(sample, today=_TODAY) is True
