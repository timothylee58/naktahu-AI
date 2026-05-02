"""Tests for app.agents.rag_node."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.rag_node import rag_node
from app.services.vector_store import ChunkResult

_FAKE_EMBEDDING = [0.1] * 1536

_FAKE_CHUNKS = [
    ChunkResult(
        id="chunk-1",
        content="Cara mendaftar syarikat dengan SSM",
        source_title="SSM Business Registration",
        source_url="https://www.ssm.com.my",
        ministry="Suruhanjaya Syarikat Malaysia",
        language="bm",
        similarity=0.88,
    )
]

_STATE = {
    "query": "Bagaimana nak daftar syarikat?",
    "language": "bm",
    "domain": "government",
}


def _mock_embed_response(embedding: list[float]) -> MagicMock:
    item = MagicMock()
    item.embedding = embedding
    resp = MagicMock()
    resp.data = [item]
    return resp


@pytest.mark.asyncio
async def test_rag_node_cache_miss_calls_search() -> None:
    """On cache miss: embed, hybrid_search, cache result, return chunks."""
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=_FAKE_CHUNKS)),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        result = await rag_node(_STATE)

    chunks = result["retrieved_chunks"]
    assert len(chunks) == 1
    assert isinstance(chunks[0], ChunkResult)
    assert chunks[0].id == "chunk-1"


@pytest.mark.asyncio
async def test_rag_node_cache_hit_skips_search() -> None:
    """On cache hit: return cached chunks without calling embed or search."""
    cached_data = [
        {
            "id": "cached-1",
            "content": "Cached content",
            "source_title": "Cached Title",
            "source_url": "https://cached.gov.my",
            "ministry": "Cached Ministry",
            "language": "en",
            "similarity": 0.75,
        }
    ]

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=cached_data)),
        patch("app.agents.rag_node.hybrid_search", AsyncMock()) as mock_search,
        patch("app.agents.rag_node.ilmu_client") as mock_client,
    ):
        result = await rag_node(_STATE)

    mock_search.assert_not_called()
    mock_client.embeddings.create.assert_not_called()

    chunks = result["retrieved_chunks"]
    assert len(chunks) == 1
    assert chunks[0].id == "cached-1"


@pytest.mark.asyncio
async def test_rag_node_cache_key_includes_domain() -> None:
    """Different domains produce different cache keys (no cross-contamination)."""
    calls: list[str] = []

    async def fake_get(key: str) -> None:
        calls.append(key)
        return None

    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", fake_get),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=[])),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        await rag_node({**_STATE, "domain": "finance"})
        await rag_node({**_STATE, "domain": "health"})

    assert calls[0] != calls[1], "Cache keys must differ by domain"


@pytest.mark.asyncio
async def test_rag_node_empty_search_result() -> None:
    """Empty search result returns empty list without error."""
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=[])),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        result = await rag_node(_STATE)

    assert result["retrieved_chunks"] == []
