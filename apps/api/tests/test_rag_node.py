"""Tests for app.agents.rag_node."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.rag_node import _deserialize_chunks, _serialize_chunks, rag_node
# Captured before the autouse fixture patches the module attribute, so the
# dimension-check test exercises the real function, not the default mock.
from app.agents.rag_node import _embed_ilmu as _real_embed_ilmu
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


@pytest.fixture(autouse=True)
def _ilmu_path_finds_nothing():
    """Default for every test: the ILMU-first path finds no rows, so rag_node
    falls back to the OpenAI path — the path these tests assert against.
    Tests exercising ILMU itself override these patches."""
    with (
        patch("app.agents.rag_node._embed_ilmu", AsyncMock(return_value=[0.0] * 4096)),
        patch("app.agents.rag_node.hybrid_search_ilmu", AsyncMock(return_value=[])),
    ):
        yield


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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
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
        patch("app.agents.rag_node.openai_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", mock_search),
        patch("app.agents.rag_node.rerank_chunks", mock_rerank),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        result = await rag_node(_STATE)

    assert mock_search.await_args.kwargs.get("limit") == 12
    mock_rerank.assert_awaited_once()
    assert result["retrieved_chunks"] == _FAKE_CHUNKS


# ── Speculative embedding task (router_node hand-off) ──────────────────────

@pytest.mark.asyncio
async def test_rag_node_reuses_speculative_embedding_task_on_cache_miss() -> None:
    """A speculative task from router_node must be awaited instead of
    rag_node calling _embed() itself — that's the whole point of the
    hand-off (see AgentState._speculative_embedding_task's docstring)."""
    task = asyncio.ensure_future(asyncio.sleep(0, result=_FAKE_EMBEDDING))
    state = {**_STATE, "_speculative_embedding_task": task}

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.cache_svc.mark_query_seen", AsyncMock()),
        patch("app.agents.rag_node.openai_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=_FAKE_CHUNKS)) as mock_search,
    ):
        mock_client.embeddings.create = AsyncMock()  # must never be called
        result = await rag_node(state)

    mock_client.embeddings.create.assert_not_awaited()
    assert mock_search.await_args.args[1] == _FAKE_EMBEDDING
    assert len(result["retrieved_chunks"]) == 1


@pytest.mark.asyncio
async def test_rag_node_cache_hit_cancels_pending_speculative_task() -> None:
    """A same-query race (see router_node's own comment on this) can land
    a speculative task in flight even though this run turns out to be a
    cache hit — it must be cancelled, not left to run to completion for a
    result nothing will use."""
    async def _never_resolves():
        await asyncio.sleep(10)
        return _FAKE_EMBEDDING

    task = asyncio.ensure_future(_never_resolves())
    state = {**_STATE, "_speculative_embedding_task": task}

    with patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=_serialize_chunks(_FAKE_CHUNKS))):
        result = await rag_node(state)

    assert task.cancelled() or task.cancelling() > 0
    assert len(result["retrieved_chunks"]) == 1
    task.cancel()  # ensure cleanup regardless of which branch fired above
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_rag_node_marks_query_seen_after_successful_cache_write() -> None:
    embed_resp = _mock_embed_response(_FAKE_EMBEDDING)

    with (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.cache_svc.mark_query_seen", AsyncMock()) as mock_mark,
        patch("app.agents.rag_node.openai_client") as mock_client,
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=_FAKE_CHUNKS)),
    ):
        mock_client.embeddings.create = AsyncMock(return_value=embed_resp)
        await rag_node(_STATE)

    mock_mark.assert_awaited_once_with(_STATE["query"], ttl=3600)


# ── Dual-embedding invariant (migration 051) ───────────────────────────────
# document_chunks.embedding is OpenAI (1536); embedding_ilmu is ILMU (4096).
# rag_node searches ILMU first and falls back to OpenAI. The rule these tests
# pin: each search function is only ever called with its own model's vector.

_ILMU_EMBEDDING = [0.2] * 4096
_ILMU_CHUNKS = [
    ChunkResult(
        id="ilmu-chunk",
        content="Geran perniagaan kecil",
        source_title="SME Corp",
        source_url="https://www.smecorp.gov.my",
        ministry="MEDAC",
        language="bm",
        similarity=0.91,
    )
]


def _cache_patches():
    return (
        patch("app.agents.rag_node.cache_svc.get_cached_result", AsyncMock(return_value=None)),
        patch("app.agents.rag_node.cache_svc.set_cached_result", AsyncMock()),
        patch("app.agents.rag_node.cache_svc.mark_query_seen", AsyncMock()),
    )


@pytest.mark.asyncio
async def test_ilmu_first_serves_query_without_touching_openai() -> None:
    """ILMU finds rows -> they're returned; the OpenAI embed and search never run."""
    c1, c2, c3 = _cache_patches()
    with (
        c1, c2, c3,
        patch("app.agents.rag_node._embed_ilmu", AsyncMock(return_value=_ILMU_EMBEDDING)),
        patch("app.agents.rag_node.hybrid_search_ilmu", AsyncMock(return_value=_ILMU_CHUNKS)) as ilmu_search,
        patch("app.agents.rag_node._embed", AsyncMock()) as openai_embed,
        patch("app.agents.rag_node.hybrid_search", AsyncMock()) as openai_search,
    ):
        result = await rag_node(_STATE)

    assert [c.id for c in result["retrieved_chunks"]] == ["ilmu-chunk"]
    # ILMU search got the ILMU vector, nothing else.
    assert ilmu_search.await_args.args[1] == _ILMU_EMBEDDING
    openai_embed.assert_not_awaited()
    openai_search.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ilmu_embed, ilmu_search",
    [
        (AsyncMock(side_effect=RuntimeError("ILMU 404 model_not_found")), AsyncMock()),
        (AsyncMock(return_value=_ILMU_EMBEDDING), AsyncMock(side_effect=RuntimeError("function hybrid_search_ilmu does not exist"))),
        (AsyncMock(return_value=_ILMU_EMBEDDING), AsyncMock(return_value=[])),
    ],
    ids=["ilmu-embed-fails", "migration-051-not-applied", "rows-not-backfilled"],
)
async def test_falls_back_to_openai_when_ilmu_path_unavailable(ilmu_embed, ilmu_search) -> None:
    """Every ILMU failure mode degrades to the OpenAI column, never to no answer."""
    c1, c2, c3 = _cache_patches()
    with (
        c1, c2, c3,
        patch("app.agents.rag_node._embed_ilmu", ilmu_embed),
        patch("app.agents.rag_node.hybrid_search_ilmu", ilmu_search),
        patch("app.agents.rag_node._embed", AsyncMock(return_value=_FAKE_EMBEDDING)),
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=_FAKE_CHUNKS)) as openai_search,
    ):
        result = await rag_node(_STATE)

    assert [c.id for c in result["retrieved_chunks"]] == ["chunk-1"]
    # The OpenAI search got the OpenAI vector — never the ILMU one.
    assert openai_search.await_args.args[1] == _FAKE_EMBEDDING


@pytest.mark.asyncio
async def test_no_chunks_when_both_providers_fail() -> None:
    """Both down -> empty retrieval (analyst_node then asks to rephrase), never
    a search run with a vector we couldn't legitimately produce."""
    c1, c2, c3 = _cache_patches()
    with (
        c1, c2, c3,
        patch("app.agents.rag_node._embed_ilmu", AsyncMock(side_effect=RuntimeError("ilmu down"))),
        patch("app.agents.rag_node._embed", AsyncMock(side_effect=RuntimeError("openai down"))),
        patch("app.agents.rag_node.hybrid_search", AsyncMock()) as openai_search,
    ):
        result = await rag_node(_STATE)

    assert result["retrieved_chunks"] == []
    openai_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_ilmu_success_cancels_unused_speculative_openai_task() -> None:
    """router_node's speculative task embeds with OpenAI; when ILMU serves the
    query it's never needed and must be cancelled, not left running."""
    async def _slow_embed():
        await asyncio.sleep(10)
        return _FAKE_EMBEDDING

    task = asyncio.create_task(_slow_embed())
    c1, c2, c3 = _cache_patches()
    with (
        c1, c2, c3,
        patch("app.agents.rag_node._embed_ilmu", AsyncMock(return_value=_ILMU_EMBEDDING)),
        patch("app.agents.rag_node.hybrid_search_ilmu", AsyncMock(return_value=_ILMU_CHUNKS)),
    ):
        await rag_node({**_STATE, "_speculative_embedding_task": task})

    await asyncio.sleep(0)
    assert task.cancelled()


@pytest.mark.asyncio
async def test_embed_uses_openai_corpus_model_and_never_ilmu() -> None:
    """_embed writes/queries the `embedding` column, so it must be the OpenAI
    model — and must raise (not silently switch provider) when unavailable."""
    from app.agents.rag_node import _embed
    from app.services.llm_client import OPENAI_EMBEDDING_MODEL

    with patch("app.agents.rag_node.openai_client") as oa, patch("app.agents.rag_node.ilmu_client") as ilmu:
        oa.embeddings.create = AsyncMock(return_value=_mock_embed_response(_FAKE_EMBEDDING))
        assert await _embed("x") == _FAKE_EMBEDDING
        assert oa.embeddings.create.await_args.kwargs["model"] == OPENAI_EMBEDDING_MODEL
        ilmu.embeddings.create.assert_not_called()

    with patch("app.agents.rag_node.openai_client", None):
        with pytest.raises(RuntimeError):
            await _embed("x")


@pytest.mark.asyncio
async def test_embed_ilmu_rejects_wrong_dimension() -> None:
    """A wrong ILMU_EMBEDDING_MODEL (e.g. one returning 1536 dims) must fail
    clearly, not be written into or searched against the 4096 column."""
    with patch("app.agents.rag_node.ilmu_client") as ilmu:
        ilmu.embeddings.create = AsyncMock(return_value=_mock_embed_response([0.1] * 1536))
        with pytest.raises(ValueError, match="1536 dims, expected 4096"):
            await _real_embed_ilmu("x")


@pytest.mark.asyncio
async def test_other_query_paths_use_the_corpus_embedder() -> None:
    """tools.query_rag and grant_rag_node search the OpenAI `embedding` column,
    so they must embed through rag_node._embed — not keep their own copy (which
    is how they previously drifted onto a different model than the corpus)."""
    import app.agents.eligibility_agent.grant_rag_node as grant_rag_node
    import app.agents.tools as tools_module

    with patch("app.agents.rag_node._embed", AsyncMock(return_value=_FAKE_EMBEDDING)) as corpus_embed:
        assert await tools_module._embed("q") == _FAKE_EMBEDDING
        assert await grant_rag_node._embed_query("q") == _FAKE_EMBEDDING
    assert corpus_embed.await_count == 2
