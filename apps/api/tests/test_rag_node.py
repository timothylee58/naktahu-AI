"""Tests for app.agents.rag_node."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.rag_node import _deserialize_chunks, _serialize_chunks, rag_node
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
async def test_rag_node_unclassified_domain_searches_everything() -> None:
    """A None domain (router couldn't classify — ILMU down, malformed
    response, etc.) must be passed through to hybrid_search as None, not
    coerced to a specific domain. hybrid_search treats domain=None as
    search-everything; silently substituting a specific domain here has
    caused every misclassified query to retrieve zero chunks whenever
    that domain happened to be empty (this exact bug shipped to
    production — see CLAUDE.md Trap #6)."""
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=_FAKE_CHUNKS)) as mock_search,
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        result = await rag_node({"query": "Something unclassifiable", "language": "en", "domain": None})

    assert mock_search.call_args.kwargs["domain"] is None
    assert len(result["retrieved_chunks"]) == 1


@pytest.mark.asyncio
async def test_rag_node_missing_domain_key_searches_everything() -> None:
    """Same as above, but for state that never had a domain key set at
    all (not just explicitly None) — must not default to a specific
    domain."""
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=_FAKE_CHUNKS)) as mock_search,
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        await rag_node({"query": "Something unclassifiable", "language": "en"})

    assert mock_search.call_args.kwargs["domain"] is None


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


def test_cache_roundtrip_preserves_freshness_fields() -> None:
    """serialize→deserialize must not drop the freshness columns; losing them
    would silently disable analyst_node's staleness / superseded checks on every
    cache hit."""
    chunk = ChunkResult(
        id="chunk-1",
        content="epf withdrawal cap rm1000",
        source_title="KWSP 2023",
        source_url="https://www.kwsp.gov.my/old",
        ministry="KWSP",
        language="en",
        similarity=0.9,
        expiry_aware=True,
        source_date="2023-01-01",
        effective_date="2023-03-15",
        superseded_by="new-chunk-id",
    )

    restored = _deserialize_chunks(_serialize_chunks([chunk]))[0]

    assert restored.expiry_aware is True
    assert restored.source_date == "2023-01-01"
    assert restored.effective_date == "2023-03-15"
    assert restored.superseded_by == "new-chunk-id"


def test_deserialize_tolerates_legacy_cache_entries() -> None:
    """Cache entries written before the freshness columns existed must still
    deserialize (with sane defaults) rather than raising KeyError."""
    legacy = [
        {
            "id": "legacy-1",
            "content": "old cached content",
            "source_title": "Old Title",
            "source_url": "https://legacy.gov.my",
            "ministry": "Ministry",
            "language": "en",
            "similarity": 0.5,
        }
    ]

    restored = _deserialize_chunks(legacy)[0]

    assert restored.expiry_aware is False
    assert restored.effective_date is None
    assert restored.superseded_by is None


@pytest.mark.asyncio
async def test_rag_node_domain_fallback_retries_unfiltered() -> None:
    """When a domain-scoped search returns nothing (e.g. router misclassified the
    domain), rag_node retries once unfiltered so relevant chunks still surface."""
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)
    mock_search = AsyncMock(side_effect=[[], _FAKE_CHUNKS])

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", mock_search),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        result = await rag_node({**_STATE, "domain": "immigration"})

    assert [c.id for c in result["retrieved_chunks"]] == ["chunk-1"]
    assert mock_search.call_count == 2
    # First call scoped to the classified domain, second unfiltered.
    assert mock_search.await_args_list[0].kwargs["domain"] == "immigration"
    assert mock_search.await_args_list[1].kwargs["domain"] is None


@pytest.mark.asyncio
async def test_rag_node_no_fallback_when_first_search_hits() -> None:
    """A domain-scoped search that returns chunks must NOT trigger a second
    unfiltered query (fallback is empty-result only)."""
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)
    mock_search = AsyncMock(return_value=_FAKE_CHUNKS)

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", mock_search),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        result = await rag_node(_STATE)

    assert len(result["retrieved_chunks"]) == 1
    assert mock_search.call_count == 1


# ── RERANK_ENABLED behaviour ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_rag_node_rerank_disabled_by_default_uses_final_limit(monkeypatch) -> None:
    """RERANK_ENABLED unset: hybrid_search is called with the normal
    5-chunk limit, and rerank_chunks is never invoked — the feature flag
    must not change default behaviour."""
    monkeypatch.delenv("RERANK_ENABLED", raising=False)
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)
    mock_search = AsyncMock(return_value=_FAKE_CHUNKS)
    mock_rerank = AsyncMock()

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", mock_search),
        patch("app.agents.rag_node.rerank_chunks", mock_rerank),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        result = await rag_node(_STATE)

    assert mock_search.await_args.kwargs.get("limit") == 5
    mock_rerank.assert_not_called()
    assert len(result["retrieved_chunks"]) == 1


@pytest.mark.asyncio
async def test_rag_node_rerank_enabled_widens_pool_and_calls_reranker(monkeypatch) -> None:
    monkeypatch.setenv("RERANK_ENABLED", "true")
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)
    wide_chunks = _FAKE_CHUNKS * 3  # simulate a wider candidate pool
    mock_search = AsyncMock(return_value=wide_chunks)
    mock_rerank = AsyncMock(return_value=_FAKE_CHUNKS)

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.ilmu_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", mock_search),
        patch("app.agents.rag_node.rerank_chunks", mock_rerank),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        result = await rag_node(_STATE)

    assert mock_search.await_args.kwargs.get("limit") == 12
    mock_rerank.assert_awaited_once()
    assert result["retrieved_chunks"] == _FAKE_CHUNKS
