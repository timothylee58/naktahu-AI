"""Tests for scripts/check_domain_coverage.py."""
from __future__ import annotations

from unittest.mock import MagicMock

from scripts.check_domain_coverage import (
    _VALID_DOMAINS,
    _chunk_counts,
    _registered_source_counts,
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


def test_main_degrades_without_crashing_when_credentials_missing(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    main()  # must not raise
    out = capsys.readouterr().out
    assert "not set" in out
    assert "education" in out  # falls back to registered-source-only listing


def test_main_degrades_without_crashing_when_supabase_unreachable(monkeypatch, capsys):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")

    def _raise_create_client(*a, **k):
        raise ConnectionError("simulated network failure")

    import scripts.check_domain_coverage as mod
    monkeypatch.setattr("supabase.create_client", _raise_create_client)

    mod.main()  # must not raise
    out = capsys.readouterr().out
    assert "Could not query document_chunks" in out
