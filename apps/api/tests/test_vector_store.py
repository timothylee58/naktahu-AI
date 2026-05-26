"""Tests for app.services.vector_store.hybrid_search.

Supabase and the async client are fully mocked so no live credentials
or network calls are required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.vector_store import ChunkResult, hybrid_search


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(
    *,
    id: str = "00000000-0000-0000-0000-000000000001",
    content: str = "Contoh kandungan teks.",
    source_title: str = "LHDN FAQ",
    source_url: str = "https://www.hasil.gov.my/en/individual/",
    ministry: str = "Lembaga Hasil Dalam Negeri Malaysia",
    language: str = "bm",
    similarity: float = 0.85,
) -> dict:
    return {
        "id": id,
        "content": content,
        "source_title": source_title,
        "source_url": source_url,
        "ministry": ministry,
        "language": language,
        "similarity": similarity,
    }


FAKE_EMBEDDING: list[float] = [0.1] * 1536


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_supabase_client() -> AsyncMock:
    """Return a fully async-mocked Supabase client."""
    execute_result = MagicMock()
    execute_result.data = [
        _make_row(id="aaaa-1", content="First result", similarity=0.92),
        _make_row(id="bbbb-2", content="Second result", similarity=0.75),
    ]

    rpc_chain = MagicMock()
    rpc_chain.execute = AsyncMock(return_value=execute_result)

    client = AsyncMock()
    client.rpc = MagicMock(return_value=rpc_chain)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hybrid_search_returns_chunk_results(mock_supabase_client: AsyncMock) -> None:
    """hybrid_search should return a list of ChunkResult dataclass instances."""
    with patch(
        "app.services.vector_store._get_client",
        AsyncMock(return_value=mock_supabase_client),
    ):
        results = await hybrid_search(
            query="cukai pendapatan individu",
            embedding=FAKE_EMBEDDING,
            domain="finance",
            limit=5,
        )

    assert isinstance(results, list)
    assert len(results) == 2
    for r in results:
        assert isinstance(r, ChunkResult)


@pytest.mark.asyncio
async def test_hybrid_search_fields_mapped_correctly(mock_supabase_client: AsyncMock) -> None:
    """All ChunkResult fields must be mapped from the RPC row data."""
    with patch(
        "app.services.vector_store._get_client",
        AsyncMock(return_value=mock_supabase_client),
    ):
        results = await hybrid_search(
            query="first result query",
            embedding=FAKE_EMBEDDING,
            domain=None,
            limit=5,
        )

    first = results[0]
    assert first.id == "aaaa-1"
    assert first.content == "First result"
    assert first.source_title == "LHDN FAQ"
    assert first.source_url == "https://www.hasil.gov.my/en/individual/"
    assert first.ministry == "Lembaga Hasil Dalam Negeri Malaysia"
    assert first.language == "bm"
    assert abs(first.similarity - 0.92) < 1e-6


@pytest.mark.asyncio
async def test_hybrid_search_similarity_is_float(mock_supabase_client: AsyncMock) -> None:
    """similarity must be cast to float even if the DB returns a string."""
    execute_result = MagicMock()
    execute_result.data = [_make_row(similarity="0.77")]  # type: ignore[arg-type]
    mock_supabase_client.rpc.return_value.execute = AsyncMock(return_value=execute_result)

    with patch(
        "app.services.vector_store._get_client",
        AsyncMock(return_value=mock_supabase_client),
    ):
        results = await hybrid_search("test", FAKE_EMBEDDING, domain=None)

    assert isinstance(results[0].similarity, float)
    assert abs(results[0].similarity - 0.77) < 1e-6


@pytest.mark.asyncio
async def test_hybrid_search_empty_result(mock_supabase_client: AsyncMock) -> None:
    """hybrid_search should return an empty list when the RPC returns no rows."""
    execute_result = MagicMock()
    execute_result.data = []
    mock_supabase_client.rpc.return_value.execute = AsyncMock(return_value=execute_result)

    with patch(
        "app.services.vector_store._get_client",
        AsyncMock(return_value=mock_supabase_client),
    ):
        results = await hybrid_search("no match query", FAKE_EMBEDDING, domain="legal")

    assert results == []


@pytest.mark.asyncio
async def test_hybrid_search_none_data(mock_supabase_client: AsyncMock) -> None:
    """hybrid_search should handle resp.data=None gracefully."""
    execute_result = MagicMock()
    execute_result.data = None
    mock_supabase_client.rpc.return_value.execute = AsyncMock(return_value=execute_result)

    with patch(
        "app.services.vector_store._get_client",
        AsyncMock(return_value=mock_supabase_client),
    ):
        results = await hybrid_search("edge case", FAKE_EMBEDDING, domain=None)

    assert results == []


@pytest.mark.asyncio
async def test_hybrid_search_rpc_called_with_domain(mock_supabase_client: AsyncMock) -> None:
    """domain_filter must be included in the RPC params when domain is provided."""
    with patch(
        "app.services.vector_store._get_client",
        AsyncMock(return_value=mock_supabase_client),
    ):
        await hybrid_search("skim caruman epf", FAKE_EMBEDDING, domain="finance", limit=3)

    call_kwargs = mock_supabase_client.rpc.call_args
    params = call_kwargs[0][1]  # second positional arg = params dict
    assert params["domain_filter"] == "finance"
    assert params["match_count"] == 3


@pytest.mark.asyncio
async def test_hybrid_search_rpc_called_without_domain(mock_supabase_client: AsyncMock) -> None:
    """domain_filter must be absent from RPC params when domain is None."""
    with patch(
        "app.services.vector_store._get_client",
        AsyncMock(return_value=mock_supabase_client),
    ):
        await hybrid_search("general query", FAKE_EMBEDDING, domain=None, limit=5)

    call_kwargs = mock_supabase_client.rpc.call_args
    params = call_kwargs[0][1]
    assert "domain_filter" not in params
