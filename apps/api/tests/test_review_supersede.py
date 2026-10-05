"""Tests for scripts.review_supersede (the supersede review CLI)."""
from __future__ import annotations

from unittest.mock import MagicMock

from scripts.review_supersede import approve, list_pending, reject


def test_approve_calls_rpc_and_reports_window_close(capsys):
    sb = MagicMock()
    sb.rpc.return_value.execute.return_value = MagicMock(data="window_closed")

    assert approve(sb, "cand-1") == "window_closed"
    sb.rpc.assert_called_once_with("approve_supersede", {"candidate_id": "cand-1"})
    assert "closed the day before the new rule starts" in capsys.readouterr().out


def test_reject_calls_rpc():
    sb = MagicMock()
    reject(sb, "cand-1")
    sb.rpc.assert_called_once_with("reject_supersede", {"candidate_id": "cand-1"})


def test_list_pending_shows_both_sides_of_each_pair(capsys):
    candidates = MagicMock(data=[{"id": "cand-1", "new_chunk_id": "n", "old_chunk_id": "o", "similarity": 0.9}])
    chunks = MagicMock(data=[
        {"id": "n", "source_title": "Relief 2027", "effective_date": "2027-01-01", "content": "RM3,000"},
        {"id": "o", "source_title": "Relief 2026", "effective_date": "2026-01-01", "content": "RM2,500"},
    ])
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = candidates
    sb.table.return_value.select.return_value.in_.return_value.execute.return_value = chunks

    assert list_pending(sb) == 1
    out = capsys.readouterr().out
    assert "Relief 2027" in out and "Relief 2026" in out and "cand-1" in out


def test_list_pending_empty(capsys):
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
    assert list_pending(sb) == 0
    assert "No pending" in capsys.readouterr().out
