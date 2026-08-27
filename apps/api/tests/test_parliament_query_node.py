"""Tests for app.agents.parliament_query_node — the structured Parliament
lookup short-circuit (bill vote record / MP-by-name), and graph.py's
conditional routing into/around it."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.graph import _route_after_guard
from app.agents.parliament_query_node import parliament_query_node


@pytest.fixture(autouse=True)
def _patch_stream_writer():
    """parliament_query_node calls get_stream_writer() on every path —
    stub it so tests don't depend on a live LangGraph execution context
    (same pattern as test_warung_watch_node.py)."""
    with patch("app.agents.parliament_query_node.get_stream_writer") as mock_writer:
        mock_writer.return_value = MagicMock()
        yield mock_writer


@pytest.mark.asyncio
async def test_streams_the_answer(_patch_stream_writer):
    """Regression guard: the SSE endpoint only ever sees `custom`-stream
    (get_stream_writer) output as `token` events — streaming_token_buffer
    alone is silently dropped."""
    write = MagicMock()
    _patch_stream_writer.return_value = write

    with patch("app.agents.parliament_query_node._get_client", return_value=None):
        result = await parliament_query_node(
            {"parliament_bill_number": "RUU 355", "parliament_mp_query": None, "language": "en"}
        )

    write.assert_called_once_with(result["streaming_token_buffer"])


@pytest.mark.asyncio
async def test_no_client_configured_degrades_gracefully():
    with patch("app.agents.parliament_query_node._get_client", return_value=None):
        result = await parliament_query_node(
            {"parliament_bill_number": "RUU 355", "parliament_mp_query": None, "language": "en"}
        )

    assert "temporarily unavailable" in result["streaming_token_buffer"]
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_missing_both_entities_never_crashes():
    result = await parliament_query_node(
        {"parliament_bill_number": None, "parliament_mp_query": None, "language": "en"}
    )
    assert "streaming_token_buffer" in result
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_bill_vote_summary_formats_breakdown_and_citation():
    mock_client = MagicMock()
    with patch("app.agents.parliament_query_node._get_client", return_value=mock_client), \
         patch(
             "app.agents.parliament_query_node.get_bill_vote_summary",
             new=AsyncMock(return_value=[{"vote": "for", "vote_count": 120}, {"vote": "against", "vote_count": 45}]),
         ):
        result = await parliament_query_node(
            {"parliament_bill_number": "RUU 355", "parliament_mp_query": None, "language": "en"}
        )

    assert "RUU 355" in result["streaming_token_buffer"]
    assert "for: 120" in result["streaming_token_buffer"]
    assert "against: 45" in result["streaming_token_buffer"]
    assert len(result["citations"]) == 1
    assert result["citations"][0]["ministry"] == "Parlimen Malaysia"
    assert result["citations"][0]["confidence"] == 1.0


@pytest.mark.asyncio
async def test_bill_vote_summary_bm_language():
    mock_client = MagicMock()
    with patch("app.agents.parliament_query_node._get_client", return_value=mock_client), \
         patch(
             "app.agents.parliament_query_node.get_bill_vote_summary",
             new=AsyncMock(return_value=[{"vote": "for", "vote_count": 5}]),
         ):
        result = await parliament_query_node(
            {"parliament_bill_number": "RUU 355", "parliament_mp_query": None, "language": "bm"}
        )

    assert "Rekod pengundian" in result["streaming_token_buffer"]


@pytest.mark.asyncio
async def test_bill_not_found_returns_no_match_message_not_crash():
    mock_client = MagicMock()
    with patch("app.agents.parliament_query_node._get_client", return_value=mock_client), \
         patch("app.agents.parliament_query_node.get_bill_vote_summary", new=AsyncMock(return_value=[])):
        result = await parliament_query_node(
            {"parliament_bill_number": "NONEXISTENT", "parliament_mp_query": None, "language": "en"}
        )

    assert "No vote records found" in result["streaming_token_buffer"]
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_mp_lookup_formats_answer_and_citation():
    mock_client = MagicMock()
    with patch("app.agents.parliament_query_node._get_client", return_value=mock_client), \
         patch(
             "app.agents.parliament_query_node.search_mps",
             new=AsyncMock(return_value=[{
                 "full_name": "Jane Doe",
                 "party": "PKR",
                 "constituency_name": "Bangi",
                 "parlimen_url": "https://parlimen.gov.my/mp/jane-doe",
             }]),
         ):
        result = await parliament_query_node(
            {"parliament_bill_number": None, "parliament_mp_query": "Bangi", "language": "en"}
        )

    assert "Jane Doe" in result["streaming_token_buffer"]
    assert "Bangi" in result["streaming_token_buffer"]
    assert result["citations"][0]["url"] == "https://parlimen.gov.my/mp/jane-doe"


@pytest.mark.asyncio
async def test_mp_lookup_falls_back_to_parlimen_url_when_missing():
    mock_client = MagicMock()
    with patch("app.agents.parliament_query_node._get_client", return_value=mock_client), \
         patch(
             "app.agents.parliament_query_node.search_mps",
             new=AsyncMock(return_value=[{"full_name": "Jane Doe", "party": "PKR", "constituency_name": "Bangi"}]),
         ):
        result = await parliament_query_node(
            {"parliament_bill_number": None, "parliament_mp_query": "Bangi", "language": "en"}
        )

    assert result["citations"][0]["url"] == "https://www.parlimen.gov.my"


@pytest.mark.asyncio
async def test_mp_not_found_returns_no_match_message_not_crash():
    mock_client = MagicMock()
    with patch("app.agents.parliament_query_node._get_client", return_value=mock_client), \
         patch("app.agents.parliament_query_node.search_mps", new=AsyncMock(return_value=[])):
        result = await parliament_query_node(
            {"parliament_bill_number": None, "parliament_mp_query": "Nonexistent Place", "language": "en"}
        )

    assert "No MP records found" in result["streaming_token_buffer"]
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_db_error_degrades_gracefully():
    mock_client = MagicMock()
    with patch("app.agents.parliament_query_node._get_client", return_value=mock_client), \
         patch(
             "app.agents.parliament_query_node.get_bill_vote_summary",
             new=AsyncMock(side_effect=RuntimeError("connection reset")),
         ):
        result = await parliament_query_node(
            {"parliament_bill_number": "RUU 355", "parliament_mp_query": None, "language": "en"}
        )

    assert "temporarily unavailable" in result["streaming_token_buffer"]


# ── graph routing ─────────────────────────────────────────────────────────
# parliament_query branches off AFTER guard (not directly off router) so
# every structured-lookup query still passes guard_node's harmful-intent
# check first — same reasoning as warung_watch (see graph.py's module
# docstring).

def test_route_after_guard_sends_bill_query_to_parliament_query():
    state = {
        "error": None,
        "is_live_status_query": False,
        "place_name": None,
        "is_structured_parliament_query": True,
        "parliament_bill_number": "RUU 355",
        "parliament_mp_query": None,
    }
    assert _route_after_guard(state) == "parliament_query"


def test_route_after_guard_sends_mp_query_to_parliament_query():
    state = {
        "error": None,
        "is_live_status_query": False,
        "place_name": None,
        "is_structured_parliament_query": True,
        "parliament_bill_number": None,
        "parliament_mp_query": "Bangi",
    }
    assert _route_after_guard(state) == "parliament_query"


def test_route_after_guard_sends_general_hansard_question_to_rag():
    state = {
        "error": None,
        "is_live_status_query": False,
        "place_name": None,
        "is_structured_parliament_query": False,
        "parliament_bill_number": None,
        "parliament_mp_query": None,
    }
    assert _route_after_guard(state) == "rag"


def test_route_after_guard_ignores_structured_flag_without_entity():
    state = {
        "error": None,
        "is_live_status_query": False,
        "place_name": None,
        "is_structured_parliament_query": True,
        "parliament_bill_number": None,
        "parliament_mp_query": None,
    }
    assert _route_after_guard(state) == "rag"


def test_route_after_guard_blocked_query_ends_even_if_flagged_structured():
    """A blocked verdict always wins — guard's refusal takes priority over
    routing to parliament_query, regardless of how router_node classified
    the query."""
    from langgraph.graph import END

    state = {
        "error": "blocked",
        "is_live_status_query": False,
        "place_name": None,
        "is_structured_parliament_query": True,
        "parliament_bill_number": "RUU 355",
        "parliament_mp_query": None,
    }
    assert _route_after_guard(state) == END
