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

continue_eligibility_agent had the exact same `ainvoke(None, config)` bug —
found while fixing an adjacent Cursor Bugbot finding on PR #153 (History
resume showing stale Grant Finder results) and confirmed by reading
eligibility_agent/graph.py directly: _route_after_intake also sends
incomplete intake straight to END with no interrupt(). Fixed the same way.
continue_study_agent and continue_eligibility_agent also never called
_log_run() on continue turns at all (only their start_* handlers did) — a
separate, real bug (History links to multi-turn sessions always resumed to
turn-1's stale data) fixed alongside the ainvoke fix for eligibility-agent,
and standalone for study-agent (whose continue never had the ainvoke bug —
it updates state directly via aupdate_state + explicit node calls, not
ainvoke — only the missing _log_run needed fixing there).

These tests exercise the real compiled graphs end-to-end via MemorySaver,
not mocked handlers, specifically to catch this class of bug — router-level
tests that patch the handler entirely would never have caught it.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agents.checkpointer import reset_checkpointer_for_tests
from app.agents.eligibility_agent.graph import get_eligibility_agent_graph
from app.agents.immigration_navigator.graph import get_immigration_navigator_graph
from app.agents.retrenchment_navigator.graph import get_retrenchment_navigator_graph
from app.agents.study_agent.graph import get_study_agent_graph
from app.services.agent_runner import (
    continue_eligibility_agent,
    continue_immigration_navigator,
    continue_retrenchment_navigator,
    continue_study_agent,
)


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


@pytest.mark.asyncio
async def test_continue_eligibility_agent_advances_state_on_second_turn():
    """Same class of bug as immigration/retrenchment above, found on this
    agent afterward — verifies current_turn actually advances (proving the
    graph really re-ran) rather than repeating turn 1's stale intake
    question forever."""
    cp = MemorySaver()
    graph = get_eligibility_agent_graph(checkpointer=cp)
    session_id = "elig-turn-test"

    with patch("app.agents.eligibility_agent.intake_node.llm_complete", AsyncMock(return_value="{}")):
        await graph.ainvoke(
            {
                "session_id": session_id,
                "user_id": "u1",
                "language": "en",
                "current_turn": 0,
                "messages": [],
                "latest_user_input": "I run a small tech startup",
                "business_profile": None,
                "intake_complete": False,
                "needs_more_info": True,
                "needs_clarification": False,
            },
            config={"configurable": {"thread_id": session_id}},
        )
        turn1_state = await graph.aget_state({"configurable": {"thread_id": session_id}})
        assert turn1_state.values.get("intake_complete") is False
        turn_before = turn1_state.values.get("current_turn")

        result = await continue_eligibility_agent(
            session_id=session_id,
            payload={"message": "Sdn Bhd, technology sector, registered 8 months ago"},
            supabase_client=None,
            checkpointer=cp,
        )

    # The bug: without the ainvoke fix, this second call is a no-op —
    # current_turn never advances and the same first question repeats.
    assert result["output"] is not None
    turn2_state = await graph.aget_state({"configurable": {"thread_id": session_id}})
    assert turn2_state.values.get("current_turn") > turn_before


@pytest.mark.asyncio
async def test_continue_eligibility_agent_logs_run_for_history_resume():
    """Confirmed Cursor Bugbot finding: continue_eligibility_agent never
    called _log_run at all — only start_eligibility_agent did — so a
    History link to a multi-turn Grant Finder session always resumed to
    turn-1's awaiting_hitl status and first-turn output, no matter how far
    the real conversation had progressed."""
    cp = MemorySaver()
    graph = get_eligibility_agent_graph(checkpointer=cp)
    session_id = "elig-log-test"
    sb = MagicMock()

    with patch("app.agents.eligibility_agent.intake_node.llm_complete", AsyncMock(return_value="{}")):
        await graph.ainvoke(
            {
                "session_id": session_id,
                "user_id": "u1",
                "language": "en",
                "current_turn": 0,
                "messages": [],
                "latest_user_input": "startup",
                "business_profile": None,
                "intake_complete": False,
                "needs_more_info": True,
                "needs_clarification": False,
            },
            config={"configurable": {"thread_id": session_id}},
        )
        await continue_eligibility_agent(
            session_id=session_id,
            payload={"message": "more details"},
            supabase_client=sb,
            checkpointer=cp,
        )

    sb.table.assert_any_call("agent_runs")


@pytest.mark.asyncio
async def test_continue_study_agent_logs_run_for_history_resume():
    """Confirmed Cursor Bugbot finding: continue_study_agent never called
    _log_run — a History link to a multi-turn study session always
    resumed to turn-1's stale explanations no matter how many follow-up
    questions were asked since."""
    cp = MemorySaver()
    graph = get_study_agent_graph(checkpointer=cp)
    session_id = "study-log-test"
    sb = MagicMock()

    with (
        patch("app.agents.study_agent.nodes.extract_questions_from_text", return_value=["Soalan 1: Apa?"]),
        patch("app.agents.study_agent.nodes.query_rag_findings", AsyncMock(return_value=[])),
        patch("app.agents.study_agent.nodes.llm_complete", AsyncMock(return_value="Jawapan.")),
    ):
        await graph.ainvoke(
            {
                "session_id": session_id,
                "user_id": "u1",
                "subject": "sejarah",
                "paper_text": "Soalan 1: Apa?",
                "document_base64": "",
                "message": "",
                "language": "bm",
                "turns_count": 0,
                "tool_calls": [],
            },
            config={"configurable": {"thread_id": session_id}},
        )
        await continue_study_agent(
            session_id=session_id,
            payload={"message": "Explain question 1 more"},
            supabase_client=sb,
            checkpointer=cp,
        )

    sb.table.assert_any_call("agent_runs")
