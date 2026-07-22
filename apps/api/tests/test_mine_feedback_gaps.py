"""Tests for scripts.mine_feedback_gaps — the negative-feedback miner."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from scripts.mine_feedback_gaps import _best_score


def _row(query: str, domain: str = "epf", rating: int = -1, language: str = "en") -> dict:
    return {"query": query, "domain": domain, "language": language, "rating": rating, "created_at": "2026-01-01T00:00:00Z"}


def test_best_score_uses_top_three_average_not_single_best():
    """A single strong chunk plus weaker corroborators must average, not
    just return the single best score — matches analyst_node exactly."""
    chunks = [
        {"source_title": "T", "source_url": "https://www.kwsp.gov.my/a", "content": "epf withdrawal age 55 first home purchase"},
        {"source_title": "T", "source_url": "https://www.kwsp.gov.my/b", "content": "epf contribution rate"},
        {"source_title": "T", "source_url": "https://www.kwsp.gov.my/c", "content": "unrelated filler text with no overlap at all"},
    ]
    score, title = _best_score("epf withdrawal age first home purchase", chunks)
    # Not the single best chunk's own score (~1.0) — averaged with weaker ones.
    assert 0.0 < score < 1.0
    assert title == "T"


def test_best_score_empty_domain_returns_zero():
    score, title = _best_score("anything", [])
    assert score == 0.0
    assert title is None


def test_mine_classifies_content_gap_vs_retrieval_issue():
    """A domain with no relevant chunks -> content_gap. A domain with a
    strong matching chunk -> retrieval_issue (content exists; the
    pipeline just didn't surface it for this user)."""
    from scripts.mine_feedback_gaps import _fetch_domain_chunks, _fetch_negative_feedback

    supabase = MagicMock()

    feedback_table = MagicMock()
    feedback_table.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=[
            _row("What should I do if I lose my MyKad?", domain="immigration"),
            _row("What is my EPF withdrawal age?", domain="epf"),
        ]
    )

    # immigration domain: only passport/visa content, nothing about MyKad
    immigration_table = MagicMock()
    immigration_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"source_title": "Passport Renewal", "source_url": "https://imi.gov.my", "content": "passport renewal visa employment pass"},
        ]
    )
    # epf domain: a chunk that directly answers the withdrawal-age query
    epf_table = MagicMock()
    epf_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"source_title": "EPF Withdrawal", "source_url": "https://kwsp.gov.my", "content": "epf withdrawal age is 55 years old"},
        ]
    )

    tables = {"feedback": feedback_table, "document_chunks": immigration_table}
    supabase.table.side_effect = lambda name: tables.get(name, feedback_table)

    rows = _fetch_negative_feedback(supabase, None)
    assert len(rows) == 2

    immigration_result = _fetch_domain_chunks(supabase, "immigration")
    score, _ = _best_score("What should I do if I lose my MyKad?", immigration_result)
    assert score < 0.6, "MyKad has no matching content — must classify as a content gap"

    tables["document_chunks"] = epf_table
    epf_result = _fetch_domain_chunks(supabase, "epf")
    score, _ = _best_score("What is my EPF withdrawal age?", epf_result)
    assert score >= 0.6, "A direct content match must classify as a retrieval issue, not a gap"


def test_write_eval_candidates_only_includes_content_gaps(tmp_path):
    from scripts.mine_feedback_gaps import _write_eval_candidates

    findings = [
        {"query": "gap query", "domain": "immigration", "created_at": "2026-01-01", "classification": "content_gap"},
        {"query": "not a gap", "domain": "epf", "created_at": "2026-01-01", "classification": "retrieval_issue"},
    ]
    out = tmp_path / "mined.jsonl"
    _write_eval_candidates(findings, out)

    lines = out.read_text().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["query"] == "gap query"
    assert parsed["expected_topic"] == "immigration"


def test_write_eval_candidates_no_gaps_writes_nothing(tmp_path):
    from scripts.mine_feedback_gaps import _write_eval_candidates

    out = tmp_path / "mined.jsonl"
    _write_eval_candidates([{"classification": "retrieval_issue"}], out)
    assert not out.exists()
