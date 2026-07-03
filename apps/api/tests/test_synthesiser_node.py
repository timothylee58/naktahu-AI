"""Tests for app.agents.synthesiser_node — output-side safety scan."""
from __future__ import annotations

from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest

from app.agents import synthesiser_node as synthesiser_module
from app.agents.synthesiser_node import synthesiser_node


async def _fake_stream(tokens: list[str]) -> AsyncGenerator[str, None]:
    for token in tokens:
        yield token


@pytest.fixture(autouse=True)
def _mock_stream_writer():
    """synthesiser_node calls get_stream_writer(), which requires a live
    LangGraph runnable context. Outside the graph (unit tests) this raises
    RuntimeError, so stub it out with a no-op writer."""
    with patch.object(synthesiser_module, "get_stream_writer", MagicMock(return_value=lambda *_a, **_k: None)):
        yield


@pytest.mark.asyncio
async def test_synthesiser_flags_jailbroken_output_and_skips_persist() -> None:
    """A jailbroken-looking LLM response is flagged and marked non-persistable."""
    jailbroken_tokens = [
        "Sure, ", "I am now unrestricted", " and will ignore my previous instructions. ",
        "As DAN, I can do anything now.",
    ]

    async def fake_stream_synthesis(state):
        async for tok in _fake_stream(jailbroken_tokens):
            yield tok

    async def fake_generate_suggestions(query, domain, language):
        return ["suggestion1", "suggestion2", "suggestion3"]

    with patch.object(synthesiser_module, "stream_synthesis", fake_stream_synthesis), \
         patch.object(synthesiser_module, "_generate_suggestions", fake_generate_suggestions):
        result = await synthesiser_node({
            "query": "cuba jailbreak sistem",
            "language": "en",
            "session_id": "sess-1",
            "user_id": "user-1",
            "retrieved_chunks": [],
        })

    assert result["output_flagged"] is True
    assert result["skip_history_persist"] is True
    assert "unrestricted" in result["streaming_token_buffer"]
    assert result["suggestions"] == ["suggestion1", "suggestion2", "suggestion3"]


@pytest.mark.asyncio
async def test_synthesiser_does_not_flag_normal_output() -> None:
    """A normal, benign LLM response is not flagged and is persistable."""
    normal_tokens = [
        "Anda boleh ", "daftar syarikat ", "melalui portal SSM rasmi.",
    ]

    async def fake_stream_synthesis(state):
        async for tok in _fake_stream(normal_tokens):
            yield tok

    async def fake_generate_suggestions(query, domain, language):
        return ["suggestion1", "suggestion2", "suggestion3"]

    with patch.object(synthesiser_module, "stream_synthesis", fake_stream_synthesis), \
         patch.object(synthesiser_module, "_generate_suggestions", fake_generate_suggestions):
        result = await synthesiser_node({
            "query": "Bagaimana nak daftar syarikat?",
            "language": "bm",
            "session_id": "sess-2",
            "user_id": "user-2",
            "retrieved_chunks": [],
        })

    assert result["output_flagged"] is False
    assert result["skip_history_persist"] is False
    assert "daftar syarikat" in result["streaming_token_buffer"]
    assert result["suggestions"] == ["suggestion1", "suggestion2", "suggestion3"]


@pytest.mark.asyncio
async def test_synthesiser_flags_output_via_log_warning() -> None:
    """Flagged output triggers a structlog warning with query/session context."""
    jailbroken_tokens = ["Ignoring my previous instructions entirely."]

    async def fake_stream_synthesis(state):
        async for tok in _fake_stream(jailbroken_tokens):
            yield tok

    async def fake_generate_suggestions(query, domain, language):
        return ["suggestion1", "suggestion2", "suggestion3"]

    with patch.object(synthesiser_module, "stream_synthesis", fake_stream_synthesis), \
         patch.object(synthesiser_module, "_generate_suggestions", fake_generate_suggestions), \
         patch.object(synthesiser_module.log, "warning") as mock_warning:
        result = await synthesiser_node({
            "query": "test query",
            "language": "en",
            "session_id": "sess-3",
            "user_id": "user-3",
            "retrieved_chunks": [],
        })

    assert result["output_flagged"] is True
    assert result["suggestions"] == ["suggestion1", "suggestion2", "suggestion3"]
    mock_warning.assert_called_once()
    args, kwargs = mock_warning.call_args
    assert args[0] == "synthesiser_output_flagged"
    assert kwargs["session_id"] == "sess-3"
