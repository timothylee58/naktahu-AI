"""Tests for KnowledgeQAAdapter.stream() — the SSE streaming path's own copy
of the needs_clarification routing (mirrors app.agents.graph._route_after_analyst;
see that function's docstring for why the split exists)."""
from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import patch

import pytest

from app.orchestration.adapters.knowledge_qa import KnowledgeQAAdapter
from app.orchestration.context import OrchestratorContext
from app.services.vector_store import ChunkResult

_FALLBACK_EN = (
    "I'm not confident enough to answer this question accurately. "
    "Could you please provide more context or rephrase your question?"
)


def _chunk() -> ChunkResult:
    return ChunkResult(
        id="c1",
        content="some retrieved content",
        source_title="Some Source",
        source_url="https://www.hasil.gov.my/some-source",
        ministry="LHDN",
        language="en",
        similarity=0.7,
    )


async def _collect(context: OrchestratorContext) -> str:
    out: list[str] = []
    async for token in KnowledgeQAAdapter().stream(context):
        out.append(token)
    return "".join(out)


async def _noop_router(state):
    return {"domain": "tax", "language": "en"}


async def _noop_guard(state):
    return {}


async def _fake_stream_synthesis(state) -> AsyncGenerator[str, None]:
    yield "hedged answer with a targeted follow-up"


@pytest.mark.asyncio
async def test_no_chunks_at_all_short_circuits_to_canned_message() -> None:
    """needs_clarification=True with nothing retrieved still gets the bare
    canned clarification message — there's no material to hedge an answer
    from."""
    async def fake_rag(state):
        return {"retrieved_chunks": []}

    async def fake_analyst(state):
        return {"needs_clarification": True, "retrieved_chunks": []}

    with patch("app.agents.router_node.router_node", _noop_router), \
         patch("app.agents.guard_node.guard_node", _noop_guard), \
         patch("app.agents.rag_node.rag_node", fake_rag), \
         patch("app.agents.analyst_node.analyst_node", fake_analyst), \
         patch("app.agents.synthesiser_node.stream_synthesis", _fake_stream_synthesis):
        text = await _collect(OrchestratorContext(query="asdf", language="en"))

    assert text == _FALLBACK_EN


@pytest.mark.asyncio
async def test_no_chunks_for_a_chinese_query_gets_the_chinese_message() -> None:
    """The streaming path used to hold its own bm/en-only copy of the
    message, so a zh query got English."""
    from app.agents.clarification import clarification_message

    async def fake_rag(state):
        return {"retrieved_chunks": []}

    async def fake_analyst(state):
        return {"needs_clarification": True, "retrieved_chunks": []}

    async def zh_router(state):
        return {"domain": "tax", "language": "zh"}

    with patch("app.agents.router_node.router_node", zh_router), \
         patch("app.agents.guard_node.guard_node", _noop_guard), \
         patch("app.agents.rag_node.rag_node", fake_rag), \
         patch("app.agents.analyst_node.analyst_node", fake_analyst):
        text = await _collect(OrchestratorContext(query="怎么办", language="zh"))

    assert text == clarification_message("zh")
    assert "抱歉" in text


@pytest.mark.asyncio
async def test_low_confidence_with_chunks_streams_hedged_answer_not_canned_message() -> None:
    """needs_clarification=True but SOME material was retrieved must stream
    through stream_synthesis (which hedges) rather than the canned message."""
    async def fake_rag(state):
        return {"retrieved_chunks": [_chunk()]}

    async def fake_analyst(state):
        return {"needs_clarification": True, "retrieved_chunks": [_chunk()]}

    with patch("app.agents.router_node.router_node", _noop_router), \
         patch("app.agents.guard_node.guard_node", _noop_guard), \
         patch("app.agents.rag_node.rag_node", fake_rag), \
         patch("app.agents.analyst_node.analyst_node", fake_analyst), \
         patch("app.agents.synthesiser_node.stream_synthesis", _fake_stream_synthesis):
        text = await _collect(OrchestratorContext(query="does my company qualify?", language="en"))

    assert text == "hedged answer with a targeted follow-up"
    assert _FALLBACK_EN not in text


@pytest.mark.asyncio
async def test_confident_answer_streams_normally() -> None:
    """needs_clarification=False is unaffected — still streams directly."""
    async def fake_rag(state):
        return {"retrieved_chunks": [_chunk()]}

    async def fake_analyst(state):
        return {"needs_clarification": False, "retrieved_chunks": [_chunk()]}

    with patch("app.agents.router_node.router_node", _noop_router), \
         patch("app.agents.guard_node.guard_node", _noop_guard), \
         patch("app.agents.rag_node.rag_node", fake_rag), \
         patch("app.agents.analyst_node.analyst_node", fake_analyst), \
         patch("app.agents.synthesiser_node.stream_synthesis", _fake_stream_synthesis):
        text = await _collect(OrchestratorContext(query="what's the SME tax rate?", language="en"))

    assert text == "hedged answer with a targeted follow-up"


@pytest.mark.asyncio
async def test_blocked_query_still_short_circuits_before_rag() -> None:
    """guard_node blocking a query must still refuse immediately — this
    change only touches the needs_clarification branch, not the guard gate."""
    async def fake_guard(state):
        return {"error": "blocked", "streaming_token_buffer": "refused"}

    async def fail_if_called(state):
        raise AssertionError("rag_node must not run for a blocked query")

    with patch("app.agents.router_node.router_node", _noop_router), \
         patch("app.agents.guard_node.guard_node", fake_guard), \
         patch("app.agents.rag_node.rag_node", fail_if_called):
        text = await _collect(OrchestratorContext(query="harmful query", language="en"))

    assert text == "refused"
