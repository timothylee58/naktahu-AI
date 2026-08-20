"""Tests for scripts/check_domain_coverage.py — the 3-axis cross-check
(registered sources x live document_chunks x eval-dataset coverage)."""
from __future__ import annotations

from unittest.mock import MagicMock

from scripts.check_domain_coverage import (
    _VALID_DOMAINS,
    _chunk_counts,
    _eval_coverage,
    _registered_source_counts,
    _status_for,
    main,
)


def test_registered_source_counts_covers_every_canonical_domain():
    counts = _registered_source_counts()
    assert set(counts) == set(_VALID_DOMAINS)
    # education was registered this session (previously 0) — a real
    # regression check, not just a shape check.
    assert counts["education"] > 0


def test_registered_source_counts_matches_real_registry_total():
    from scripts.sources import SOURCES
    counts = _registered_source_counts()
    assert sum(counts.values()) == len(SOURCES)


def test_eval_coverage_reads_both_dataset_field_names():
    # answer_quality.jsonl tags `expected_topic`, language_accuracy.jsonl
    # tags `domain` — this must read both, not just one.
    counts = _eval_coverage()
    assert set(counts) == set(_VALID_DOMAINS)
    # welfare was fixed onto this list two commits ago specifically because
    # it had zero eval coverage — real regression check that it now does.
    assert counts["welfare"] > 0


def test_eval_coverage_every_canonical_domain_has_at_least_one_case():
    # Mirrors evals/test_evals.py's own completeness assertion — if this
    # ever goes false, that OTHER test should already be failing too (the
    # two are meant to agree, not just coincidentally both pass).
    counts = _eval_coverage()
    missing = [d for d in _VALID_DOMAINS if counts[d] == 0]
    assert not missing, f"no eval coverage for domain(s): {missing}"


def _mock_client_returning(count: int, newest_iso: str | None):
    execute_result = MagicMock()
    execute_result.count = count
    execute_result.data = [{"created_at": newest_iso}] if newest_iso else []

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = execute_result

    client = MagicMock()
    client.table.return_value = chain
    return client


def test_chunk_counts_reports_zero_for_empty_domain():
    client = _mock_client_returning(0, None)
    result = _chunk_counts(client)
    assert set(result) == set(_VALID_DOMAINS)
    for domain in _VALID_DOMAINS:
        assert result[domain] == {"count": 0, "newest_created_at": None}


def test_chunk_counts_reports_real_count_and_newest_date():
    client = _mock_client_returning(42, "2026-08-01T00:00:00Z")
    result = _chunk_counts(client)
    for domain in _VALID_DOMAINS:
        assert result[domain]["count"] == 42
        assert result[domain]["newest_created_at"] == "2026-08-01T00:00:00Z"


def test_status_for_no_sources_and_no_chunks():
    assert "NO SOURCES REGISTERED" in _status_for(0, 0, n_evals=1)


def test_status_for_registered_but_never_ingested():
    assert "REGISTERED BUT NEVER INGESTED" in _status_for(2, 0, n_evals=1)


def test_status_for_content_without_registered_source():
    assert "separate pipeline" in _status_for(0, 5, n_evals=1)


def test_status_for_ok_when_everything_present():
    status = _status_for(2, 5, n_evals=1)
    assert status == "ok"


def test_status_for_flags_missing_eval_coverage_independently():
    # A domain can be otherwise "ok" (sources + chunks both present) and
    # STILL get flagged if eval coverage is the thing missing — the three
    # axes are independent, not "any two implies the third".
    status = _status_for(2, 5, n_evals=0)
    assert status == "ok | NO EVAL COVERAGE"


def test_main_runs_without_credentials_reports_sources_and_evals_only(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    result = main()  # must not raise
    out = capsys.readouterr().out
    assert "live-content axis skipped" in out
    assert "education" in out
    assert isinstance(result, int)


def test_main_exit_code_catches_no_sources_gap_without_credentials(monkeypatch, capsys):
    """Regression test for a real bug caught while building this: without
    Supabase credentials, the table correctly showed parliament as 'NO
    SOURCES REGISTERED' but the exit code stayed 0 — the gap-detection
    logic only checked n_evals when chunks was None, silently ignoring the
    axis-1-only gap that's visible without any DB access at all. parliament
    is registered as an example of exactly this: it has zero sources.py
    entries (its own separate, never-run ingest_parliament/ pipeline)."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    result = main()
    out = capsys.readouterr().out
    assert "parliament" in out and "NO SOURCES REGISTERED" in out
    assert result == 1, "table shows a real gap — exit code must not be 0"


def test_main_degrades_without_crashing_when_supabase_unreachable(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    def _raise_create_client(*a, **k):
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr("supabase.create_client", _raise_create_client)

    result = main()  # must not raise
    out = capsys.readouterr().out
    assert "Could not query document_chunks" in out
    assert isinstance(result, int)
