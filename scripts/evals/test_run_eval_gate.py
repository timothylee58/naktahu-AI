"""Tests for the deploy eval gate harness."""
from __future__ import annotations

from datetime import date

from scripts.evals.run_eval_gate import (
    FAITHFULNESS_GATE,
    compute_avg_temporal_accuracy,
    evaluate_gates,
    load_samples,
    main,
    _DEFAULT_SAMPLES,
)
from scripts.evals.temporal_scorer import TEMPORAL_ACCURACY_GATE

_TODAY = date(2026, 7, 3)


# --- score computation -----------------------------------------------------


def test_golden_fixture_is_current_and_passes_temporal_gate() -> None:
    samples = load_samples(_DEFAULT_SAMPLES)
    score = compute_avg_temporal_accuracy(samples, today=_TODAY)
    assert score >= TEMPORAL_ACCURACY_GATE
    assert score == 1.0  # the shipped golden corpus is all current


def test_stale_sample_drags_avg_below_gate() -> None:
    samples = [
        {"domain": "epf", "chunks": [{"effective_days_ago": 30, "superseded_by": None}]},
        # 3 years old in a strict domain → decays well below the gate
        {"domain": "epf", "chunks": [{"effective_days_ago": 1095, "superseded_by": None}]},
    ]
    score = compute_avg_temporal_accuracy(samples, today=_TODAY)
    assert score < TEMPORAL_ACCURACY_GATE


def test_superseded_sample_scores_zero() -> None:
    samples = [
        {"domain": "epf", "chunks": [{"effective_days_ago": 10, "superseded_by": "newer"}]},
    ]
    assert compute_avg_temporal_accuracy(samples, today=_TODAY) == 0.0


# --- gate evaluation -------------------------------------------------------


def test_both_gates_pass() -> None:
    failures, skipped = evaluate_gates({"faithfulness": 0.82, "temporal_accuracy": 0.9})
    assert failures == []
    assert skipped == []


def test_faithfulness_gate_fails() -> None:
    failures, _ = evaluate_gates({"faithfulness": 0.65, "temporal_accuracy": 0.9})
    assert any("faithfulness" in f for f in failures)


def test_temporal_gate_fails() -> None:
    failures, _ = evaluate_gates({"faithfulness": 0.9, "temporal_accuracy": 0.5})
    assert any("temporal_accuracy" in f for f in failures)


def test_missing_faithfulness_is_skipped_by_default() -> None:
    failures, skipped = evaluate_gates({"faithfulness": None, "temporal_accuracy": 0.9})
    assert failures == []
    assert "faithfulness" in skipped


def test_missing_faithfulness_is_failure_when_required() -> None:
    failures, _ = evaluate_gates(
        {"faithfulness": None, "temporal_accuracy": 0.9}, require=("faithfulness",)
    )
    assert any("faithfulness" in f for f in failures)


def test_gate_thresholds() -> None:
    assert FAITHFULNESS_GATE == 0.7
    assert TEMPORAL_ACCURACY_GATE == 0.6


# --- CLI exit codes --------------------------------------------------------


def test_main_passes_on_golden_corpus_without_faithfulness() -> None:
    # No faithfulness supplied → its gate is skipped; temporal gate passes.
    assert main(["--samples", str(_DEFAULT_SAMPLES), "--no-record"]) == 0


def test_main_fails_when_faithfulness_below_gate() -> None:
    code = main(["--samples", str(_DEFAULT_SAMPLES), "--faithfulness", "0.5", "--no-record"])
    assert code == 1


def test_main_fails_when_faithfulness_required_but_missing() -> None:
    code = main(["--samples", str(_DEFAULT_SAMPLES), "--require-faithfulness", "--no-record"])
    assert code == 1
