"""Tests for app.agents.warung_watch_node — the live-status short-circuit
answer, and graph.py's conditional routing into/around it."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.graph import _route_after_router
from app.agents.warung_watch_node import warung_watch_node


def _mock_result(data):
    res = MagicMock()
    res.data = data
    return res


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
async def test_warung_watch_node_reports_packed_status_en():
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([{"id": "w1", "name": "Pelita"}])
    )
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = AsyncMock(
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
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=_mock_result([
            {"status": "empty", "source": "user_report", "created_at": "2099-01-01T12:00:00+00:00"},
        ])
    )
    with patch("app.agents.warung_watch_node._get_client", new=AsyncMock(return_value=mock_client)):
        result = await warung_watch_node({"place_name": "Pelita", "language": "bm"})

    assert "lengang" in result["streaming_token_buffer"]


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

def test_route_after_router_sends_live_status_query_to_warung_watch():
    state = {"is_live_status_query": True, "place_name": "Pelita"}
    assert _route_after_router(state) == "warung_watch"


def test_route_after_router_sends_normal_query_to_guard():
    state = {"is_live_status_query": False, "place_name": None}
    assert _route_after_router(state) == "guard"


def test_route_after_router_ignores_flag_without_place_name():
    state = {"is_live_status_query": True, "place_name": None}
    assert _route_after_router(state) == "guard"
