"""Guards the checkpoint-serialisability of agent graph state.

Production 500 this pins down: a live Supabase `Client` was injected into
LangGraph state as `_supabase`. The checkpointer serialises every state key on
each write, and the client holds an `_thread.RLock` — neither msgpack- nor
pickle-serialisable — so `graph.ainvoke(...)` raised

    TypeError: Type is not msgpack serializable: Client

surfacing as an unhandled HTTP 500 on `/api/v1/agents/{name}/start` for all
three agents that needed a client (eligibility-agent, grant-draft-generator,
compliance-drafter). The browser reported it as a CORS error, because a request
that dies before a response has no CORS headers on it either.

The whole existing suite missed it because every test passed either `None` or a
`MagicMock` as `supabase_client`, and both of those serialise fine. These tests
deliberately use an object with the same defect as the real client (an
un-pickleable lock) so the regression cannot come back unnoticed.
"""
from __future__ import annotations

import pickle
import threading
from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver

from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.checkpointer import reset_checkpointer_for_tests
from app.agents.runtime import supabase_from_config
from app.services.agent_runner import (
    _thread_config,
    confirm_grant_draft_generator,
    continue_compliance_drafter,
    start_eligibility_agent,
    start_grant_draft_generator,
)


class FakeUnpickleableClient:
    """Stands in for supabase.Client: holds a lock, so it cannot be serialised.

    Using a fake rather than a real client keeps the test offline and free of
    supabase-py version coupling, while reproducing the exact property that
    broke production.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def table(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
        raise AssertionError("network access is not expected in this test")


@pytest.fixture(autouse=True)
def _reset_cp():
    reset_checkpointer_for_tests()
    yield
    reset_checkpointer_for_tests()


def test_fake_client_reproduces_the_real_defect():
    """Sanity-check the fixture: if this object became serialisable, the tests
    below would pass vacuously and stop guarding anything."""
    with pytest.raises((TypeError, AttributeError)):
        pickle.dumps(FakeUnpickleableClient())


def test_thread_config_carries_client_outside_state():
    """The client must ride in `configurable`, which is not checkpointed."""
    client = FakeUnpickleableClient()
    config = _thread_config("session-1", supabase=client)

    assert config["configurable"]["supabase"] is client
    assert supabase_from_config(config) is client
    # thread_id still present — resumption must keep working.
    assert config["configurable"]["thread_id"] == "session-1"


def test_thread_config_omits_key_when_no_client():
    config = _thread_config("session-1")
    assert "supabase" not in config["configurable"]
    assert supabase_from_config(config) is None


@pytest.mark.parametrize("config", [None, {}, {"configurable": {}}])
def test_supabase_from_config_degrades_to_none(config):
    """Nodes keep their Trap #4 degraded-mode behaviour instead of crashing
    when no client was provided."""
    assert supabase_from_config(config) is None


@pytest.mark.asyncio
async def test_start_eligibility_agent_survives_unserialisable_client():
    """The actual regression: this raised TypeError -> HTTP 500 before the fix."""
    result = await start_eligibility_agent(
        user_id="u1",
        payload={
            "sector": "technology",
            "business_type": "sole_prop",
            "registered_months": 18,
            "annual_revenue_myr": 250_000,
            "is_bumiputera": True,
            "language": "bm",
            "message": "",
        },
        supabase_client=FakeUnpickleableClient(),
        checkpointer=MemorySaver(),
    )

    assert result["session_id"]
    assert result["status"] in {"awaiting_hitl", "completed"}


@pytest.mark.asyncio
async def test_checkpointed_state_holds_no_client_handle():
    """Even with a client in play, nothing unserialisable lands in state —
    which is what keeps the checkpoint write from throwing."""
    cp = MemorySaver()
    session_id = "elig-serialisable"

    from app.agents.eligibility_agent.graph import get_eligibility_agent_graph

    graph = get_eligibility_agent_graph(checkpointer=cp)
    await graph.ainvoke(
        {
            "session_id": session_id,
            "user_id": "u1",
            "language": "en",
            "current_turn": 0,
            "messages": [],
            "latest_user_input": "I run a tech startup",
            "business_profile": None,
            "intake_complete": False,
            "needs_more_info": True,
            "needs_clarification": False,
        },
        config=_thread_config(session_id, supabase=FakeUnpickleableClient()),
    )

    snapshot = await graph.aget_state(_thread_config(session_id))
    assert "_supabase" not in snapshot.values
    # Belt and braces: the whole state survives a round-trip.
    pickle.dumps(dict(snapshot.values))


@pytest.mark.asyncio
async def test_confirm_grant_draft_generator_with_edits_does_not_500():
    """Confirmed cubic-dev-ai finding on this PR's own fix: passing edits
    through confirm re-runs compile_node to reflect them in report_html/
    report_json before resuming — but compile_node(state) takes exactly one
    positional argument, and an early version of this fix passed a second
    (the run config). Every edited-draft confirm would have raised
    `TypeError: compile_node() takes 1 positional argument but 2 were given`
    and 500'd. compile_node is a pure state->report builder and never reads
    Supabase, so it must never receive config at all."""
    cp = MemorySaver()
    sb = MagicMock()
    started = await start_grant_draft_generator(
        user_id="u1",
        payload={
            "programme_name": "",  # empty -> fetch_grant_node short-circuits
            "business_profile": {"sector": "technology"},
            "language": "en",
        },
        supabase_client=sb,
        checkpointer=cp,
    )
    session_id = started["session_id"]

    result = await confirm_grant_draft_generator(
        session_id=session_id,
        user_id="u1",
        user_email=None,
        supabase_client=sb,
        checkpointer=cp,
        edits={"executive_summary": "Edited summary text."},
    )
    assert "session_id" in result


@pytest.mark.asyncio
async def test_continue_compliance_drafter_accepts_supabase_client():
    """Confirmed cubic-dev-ai finding: continue_compliance_drafter had no
    supabase_client parameter at all (and the router never passed one).
    compliance_drafter's graph is compiled with
    interrupt_before=["generate_pdf"] — a continue call against a thread
    already paused there resumes straight into generate_pdf_node, which
    needs the client for the actual upload.

    No prior checkpoint exists for this session_id, so `ainvoke(None, ...)`
    runs the graph from START — the RAG query nodes are mocked out (network
    is blocked in this sandbox), matching test_agent_runner_continue.py's
    established pattern for the sibling agents."""
    cp = MemorySaver()
    with patch("app.agents.compliance_drafter.nodes.query_rag_findings", AsyncMock(return_value=[])):
        result = await continue_compliance_drafter(
            session_id="cd-arity-check",
            user_id="u1",
            payload={"context": "still checking arity, not real state"},
            checkpointer=cp,
            supabase_client=MagicMock(),
        )
    assert isinstance(result, dict)
