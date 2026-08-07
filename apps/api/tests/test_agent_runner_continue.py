"""Regression tests for the multi-turn continue() bug found by Cursor Bugbot
on PR #140: continue_immigration_navigator/continue_retrenchment_navigator
used `graph.aupdate_state(...)` + `graph.ainvoke(None, config)` to advance a
conversation. Neither graph ever calls `interrupt()` — every turn runs
START -> ... -> END, including "needs_input" turns (route_after_intake sends
incomplete intake straight to END). `ainvoke(None, config)` only resumes a
graph paused at an interrupt; called against an already-terminal thread it
is a verified no-op (zero node events fire), so turn 2 onward silently
returned turn 1's stale state forever. The fix passes the new message as
real `ainvoke` input so the graph actually restarts from START each turn.

These tests exercise the real compiled graphs end-to-end via MemorySaver,
not mocked handlers, specifically to catch this class of bug — router-level
tests that patch the handler entirely would never have caught it.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agents.checkpointer import reset_checkpointer_for_tests
from app.agents.immigration_navigator.graph import get_immigration_navigator_graph
from app.agents.retrenchment_navigator.graph import get_retrenchment_navigator_graph
from app.services.agent_runner import continue_immigration_navigator, continue_retrenchment_navigator


@pytest.fixture(autouse=True)
def _reset_cp():
    reset_checkpointer_for_tests()
    yield
    reset_checkpointer_for_tests()


@pytest.mark.asyncio
async def test_continue_immigration_navigator_advances_state_on_second_turn():
    cp = MemorySaver()
    graph = get_immigration_navigator_graph(checkpointer=cp)
    session_id = "imm-turn-test"

    with patch("app.agents.immigration_navigator.nodes.query_rag_findings", AsyncMock(return_value=[])), \
         patch("app.agents.immigration_navigator.nodes.llm_complete", AsyncMock(return_value="")):
        await graph.ainvoke(
            {"session_id": session_id, "user_id": "u1", "message": "I'm from the UK", "language": "en", "turns_count": 0, "tool_calls": []},
            config={"configurable": {"thread_id": session_id}},
        )
        turn1_state = await graph.aget_state({"configurable": {"thread_id": session_id}})
        assert turn1_state.values.get("status") == "needs_input"
        turns_before = turn1_state.values.get("turns_count")

        result = await continue_immigration_navigator(
            session_id=session_id,
            payload={"message": "I want to work here for 12 months"},
            supabase_client=None,
            checkpointer=cp,
        )

    # The bug: without the fix, this second call is a no-op — turns_count
    # never advances and status stays "needs_input" forever with the exact
    # same next_prompt repeated.
    assert result["turns_count"] > turns_before


@pytest.mark.asyncio
async def test_continue_retrenchment_navigator_completes_across_turns():
    cp = MemorySaver()
    graph = get_retrenchment_navigator_graph(checkpointer=cp)
    session_id = "retr-turn-test"

    with patch("app.agents.retrenchment_navigator.nodes.query_rag_findings", AsyncMock(return_value=[])), \
         patch("app.agents.retrenchment_navigator.nodes.llm_complete", AsyncMock(return_value="")):
        await graph.ainvoke(
            {"session_id": session_id, "user_id": "u1", "message": "I worked 3 years", "language": "en", "turns_count": 0, "tool_calls": []},
            config={"configurable": {"thread_id": session_id}},
        )
        turn1 = await graph.aget_state({"configurable": {"thread_id": session_id}})
        assert turn1.values.get("status") == "needs_input"

        result = await continue_retrenchment_navigator(
            session_id=session_id,
            payload={"message": "salary RM4500, 30 days notice, yes EIS contributor"},
            supabase_client=None,
            checkpointer=cp,
        )

    # Without the fix, this stays "needs_input" forever (repeats the salary
    # question) even though every field was just answered in one message.
    assert result["status"] == "completed"
    assert "next_prompt" not in result
