"""Tests for app.agents.warung_watch_node — the live-status short-circuit
answer, and graph.py's conditional routing into/around it."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.graph import _route_after_guard
from app.agents.warung_watch_node import warung_watch_node


def _mock_result(data):
    res = MagicMock()
    res.data = data
    return res


@pytest.fixture(autouse=True)
def _patch_stream_writer():
    """warung_watch_node calls get_stream_writer() on every path — stub it
    so tests don't depend on a live LangGraph execution context (same
    pattern as test_guard_node.py)."""
    with patch("app.agents.warung_watch_node.get_stream_writer") as mock_writer:
        mock_writer.return_value = MagicMock()
        yield mock_writer


@pytest.mark.asyncio
async def test_warung_watch_node_streams_the_answer(_patch_stream_writer):
    """Regression test for the confirmed high-severity finding: the SSE
    endpoint only ever sees `custom`-stream (get_stream_writer) output as
    `token` events — streaming_token_buffer alone is silently dropped for
    every path except needs_clarification, which this node never sets."""
    write = MagicMock()
    _patch_stream_writer.return_value = write

    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=None)):
        result = await warung_watch_node({"place_name": "Pelita", "language": "en"})

    write.assert_called_once_with(result["streaming_token_buffer"])


@pytest.mark.asyncio
async def test_warung_watch_node_no_client_configured_degrades_gracefully():
    """No SUPABASE_URL/SERVICE_ROLE_KEY in env → answer honestly, never crash."""
    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=None)):
        result = await warung_watch_node({"place_name": "Pelita", "language": "en"})

    assert "Pelita" in result["streaming_token_buffer"]
    assert "No recent status reports" in result["streaming_token_buffer"]


@pytest.mark.asyncio
async def test_warung_watch_node_no_matching_warung():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([])
    )
    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=mock_client)):
        result = await warung_watch_node({"place_name": "Nonexistent Place", "language": "en"})

    assert "No recent status reports" in result["streaming_token_buffer"]


@pytest.mark.asyncio
async def test_warung_watch_node_picks_exact_match_over_substring_match():
    """Regression test: searching "pelita" with both "Pelita" and "Restoran
    Pelita" in the candidate pool must resolve to the exact match, not
    whatever the DB happens to return first."""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([
            {"id": "w2", "name": "Restoran Pelita"},
            {"id": "w1", "name": "Pelita"},
        ])
    )
    mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([
            {"status": "packed", "source": "user_report", "created_at": "2099-01-01T12:00:00+00:00"},
        ])
    )
    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=mock_client)):
        result = await warung_watch_node({"place_name": "Pelita", "language": "en"})

    assert "Restoran Pelita" not in result["streaming_token_buffer"]
    assert "Pelita is reported" in result["streaming_token_buffer"]


@pytest.mark.asyncio
async def test_warung_watch_node_reports_packed_status_en():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([{"id": "w1", "name": "Pelita"}])
    )
    mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([
            {"status": "packed", "source": "user_report", "created_at": "2099-01-01T12:00:00+00:00"},
        ])
    )
    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=mock_client)):
        result = await warung_watch_node({"place_name": "Pelita", "language": "en"})

    assert "Pelita" in result["streaming_token_buffer"]
    assert "packed" in result["streaming_token_buffer"]
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_warung_watch_node_reports_status_bm():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([{"id": "w1", "name": "Pelita"}])
    )
    mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([
            {"status": "empty", "source": "user_report", "created_at": "2099-01-01T12:00:00+00:00"},
        ])
    )
    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=mock_client)):
        result = await warung_watch_node({"place_name": "Pelita", "language": "bm"})

    assert "lengang" in result["streaming_token_buffer"]


@pytest.mark.asyncio
async def test_warung_watch_node_ignores_reports_older_than_stale_window():
    """Regression test for the confirmed medium-severity finding: the chat
    path must apply the same 24h STALE_WINDOW the REST /status endpoint
    does, via the same .gte("created_at", ...) filter — verified here by
    asserting .gte() was actually called on the checkins query."""
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([{"id": "w1", "name": "Pelita"}])
    )
    checkins_select = mock_client.table.return_value.select.return_value
    checkins_select.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([])
    )
    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=mock_client)):
        result = await warung_watch_node({"place_name": "Pelita", "language": "en"})

    checkins_select.eq.return_value.gte.assert_called_once()
    assert "No recent status reports" in result["streaming_token_buffer"]


@pytest.mark.asyncio
async def test_warung_watch_node_db_error_degrades_gracefully():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute = AsyncMock(
        side_effect=RuntimeError("connection reset")
    )
    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=mock_client)):
        result = await warung_watch_node({"place_name": "Pelita", "language": "en"})

    assert "No recent status reports" in result["streaming_token_buffer"]


@pytest.mark.asyncio
async def test_warung_watch_node_missing_place_name_never_crashes():
    result = await warung_watch_node({"place_name": None, "language": "en"})
    assert "streaming_token_buffer" in result


# ── graph routing ─────────────────────────────────────────────────────────
# warung_watch now branches off AFTER guard (not directly off router) so
# every live-status query still passes guard_node's harmful-intent check —
# see graph.py's module docstring for the confirmed finding this fixes.

def test_route_after_guard_sends_live_status_query_to_warung_watch():
    state = {"error": None, "is_live_status_query": True, "place_name": "Pelita"}
    assert _route_after_guard(state) == "warung_watch"


def test_route_after_guard_sends_normal_query_to_rag():
    state = {"error": None, "is_live_status_query": False, "place_name": None}
    assert _route_after_guard(state) == "rag"


def test_route_after_guard_ignores_live_status_flag_without_place_name():
    state = {"error": None, "is_live_status_query": True, "place_name": None}
    assert _route_after_guard(state) == "rag"


def test_route_after_guard_blocked_query_ends_even_if_flagged_live_status():
    """A blocked verdict always wins — guard's refusal takes priority over
    routing to warung_watch, regardless of how router_node classified the
    query."""
    from langgraph.graph import END

    state = {"error": "blocked", "is_live_status_query": True, "place_name": "Pelita"}
    assert _route_after_guard(state) == END
