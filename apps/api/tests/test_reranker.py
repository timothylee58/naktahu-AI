"""Tests for app.services.reranker."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.reranker import rerank_chunks, rerank_enabled
from app.services.vector_store import ChunkResult


def _chunk(id_: str, similarity: float) -> ChunkResult:
    return ChunkResult(
        id=id_,
        content=f"Content for {id_}",
        source_title=f"Title {id_}",
        source_url="https://example.gov.my",
        ministry="Test Ministry",
        language="en",
        similarity=similarity,
    )


_CHUNKS = [_chunk("a", 0.9), _chunk("b", 0.85), _chunk("c", 0.8), _chunk("d", 0.75)]


def _mock_chat_response(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_rerank_enabled_defaults_false(monkeypatch):
    monkeypatch.delenv("RERANK_ENABLED", raising=False)
    assert rerank_enabled() is False


def test_rerank_enabled_true_values(monkeypatch):
    for val in ("true", "1", "yes", "True", "YES"):
        monkeypatch.setenv("RERANK_ENABLED", val)
        assert rerank_enabled() is True


@pytest.mark.asyncio
async def test_rerank_chunks_reorders_by_model_output(monkeypatch):
    """Model ranks [3, 1, 2, 4] (1-indexed) -> chunks c, a, b, d."""
    resp = _mock_chat_response('{"ranked_ids": [3, 1, 2, 4]}')
    monkeypatch.setattr(
        "app.services.reranker.ilmu_client.chat.completions.create",
        AsyncMock(return_value=resp),
    )
    result = await rerank_chunks(query="test query", chunks=_CHUNKS, top_n=3)
    assert [c.id for c in result] == ["c", "a", "b"]


@pytest.mark.asyncio
async def test_rerank_chunks_appends_omitted_indices(monkeypatch):
    """Model only ranks 2 of 4 candidates — the other 2 are still returned,
    appended in original order, not silently dropped."""
    resp = _mock_chat_response('{"ranked_ids": [2, 4]}')
    monkeypatch.setattr(
        "app.services.reranker.ilmu_client.chat.completions.create",
        AsyncMock(return_value=resp),
    )
    result = await rerank_chunks(query="test query", chunks=_CHUNKS, top_n=4)
    assert [c.id for c in result] == ["b", "d", "a", "c"]


@pytest.mark.asyncio
async def test_rerank_chunks_degrades_to_original_order_on_malformed_json(monkeypatch):
    resp = _mock_chat_response("not valid json at all")
    monkeypatch.setattr(
        "app.services.reranker.ilmu_client.chat.completions.create",
        AsyncMock(return_value=resp),
    )
    result = await rerank_chunks(query="test query", chunks=_CHUNKS, top_n=2)
    assert [c.id for c in result] == ["a", "b"]


@pytest.mark.asyncio
async def test_rerank_chunks_degrades_to_original_order_on_empty_ranked_ids(monkeypatch):
    resp = _mock_chat_response('{"ranked_ids": []}')
    monkeypatch.setattr(
        "app.services.reranker.ilmu_client.chat.completions.create",
        AsyncMock(return_value=resp),
    )
    result = await rerank_chunks(query="test query", chunks=_CHUNKS, top_n=2)
    assert [c.id for c in result] == ["a", "b"]


@pytest.mark.asyncio
async def test_rerank_chunks_degrades_on_api_failure(monkeypatch):
    monkeypatch.setattr(
        "app.services.reranker.ilmu_client.chat.completions.create",
        AsyncMock(side_effect=RuntimeError("ILMU unavailable")),
    )
    result = await rerank_chunks(query="test query", chunks=_CHUNKS, top_n=2)
    assert [c.id for c in result] == ["a", "b"]


@pytest.mark.asyncio
async def test_rerank_chunks_ignores_out_of_range_indices(monkeypatch):
    """A hallucinated index (e.g. 99, or 0/negative) must not raise or
    corrupt the result — just be skipped, real chunks still returned."""
    resp = _mock_chat_response('{"ranked_ids": [99, 0, -1, 2]}')
    monkeypatch.setattr(
        "app.services.reranker.ilmu_client.chat.completions.create",
        AsyncMock(return_value=resp),
    )
    result = await rerank_chunks(query="test query", chunks=_CHUNKS, top_n=4)
    assert result[0].id == "b"
    assert {c.id for c in result} == {"a", "b", "c", "d"}


@pytest.mark.asyncio
async def test_rerank_chunks_single_chunk_skips_llm_call(monkeypatch):
    mock_create = AsyncMock()
    monkeypatch.setattr("app.services.reranker.ilmu_client.chat.completions.create", mock_create)
    result = await rerank_chunks(query="q", chunks=[_chunk("only", 0.5)], top_n=5)
    assert [c.id for c in result] == ["only"]
    mock_create.assert_not_called()
