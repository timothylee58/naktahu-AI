"""Tests for the low-confidence diagnostics (analyst_node) and the bounded
retrieval retry (retrieval_retry_node + its graph routing).

No network: hybrid search and the cache are patched. Chunks are built so the
analyst's real scoring decides the outcome (gov URL +0.3, title +0.2,
relevance*0.5), rather than faking confidence values.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents import retrieval_retry_node as rr
from app.agents.analyst_node import analyse, analyst_node
from app.agents.graph import _route_after_analyst_or_retry, build_graph
from app.agents.rag_node import _cache_key, retrieve_unscoped
from app.core.prometheus_metrics import (
    retrieval_low_confidence_total,
    retrieval_retry_total,
    retrieval_score,
)
from app.services.vector_store import ChunkResult

_QUERY = "kadar cukai pendapatan"
_EMBEDDING = [0.1] * 8


def _chunk(chunk_id: str, *, similarity: float, gov: bool = True) -> ChunkResult:
    return ChunkResult(
        id=chunk_id,
        content="unrelated text about something else entirely",
        source_title="Some Source",
        source_url="https://www.hasil.gov.my/x" if gov else "https://example.com/x",
        ministry="LHDN",
        language="bm",
        similarity=similarity,
    )


# Scores 0.2 + 0.5*0.1 = 0.25 each: well under the 0.6 bar.
_WEAK = [_chunk("w1", similarity=0.1, gov=False), _chunk("w2", similarity=0.1, gov=False)]
# Score 0.3 + 0.2 + 0.5*0.9 = 0.95 each.
_STRONG = [_chunk("s1", similarity=0.9), _chunk("s2", similarity=0.9), _chunk("s3", similarity=0.9)]


async def _weak_state(**overrides) -> dict:
    """State as it leaves rag_node + a real first analyst pass on weak chunks."""
    state = {
        "query": _QUERY,
        "language": "bm",
        "domain": "government",
        "retrieved_chunks": list(_WEAK),
        "_query_embedding": _EMBEDDING,
        **overrides,
    }
    state.update(await analyst_node(state))
    return state


def _counter(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def _hist_count(hist) -> float:
    return next(s.value for s in hist.collect()[0].samples if s.name.endswith("_count"))


# ── should_retry ────────────────────────────────────────────────────────────

_ELIGIBLE = {
    "needs_clarification": True,
    "domain": "government",
    "retrieved_chunks": [_WEAK[0]],
    "_query_embedding": _EMBEDDING,
}


def test_should_retry_when_eligible() -> None:
    assert rr.should_retry(_ELIGIBLE) is True


@pytest.mark.parametrize(
    "override",
    [
        {"needs_clarification": False},
        {"domain": None},  # unscoped search would be identical
        {"retrieved_chunks": []},  # empty case is rag_node's own fallback
        {"_query_embedding": None},  # cache hit: no embedding, no retry
    ],
)
def test_should_not_retry_when_any_condition_missing(override: dict) -> None:
    assert rr.should_retry({**_ELIGIBLE, **override}) is False


def test_missing_embedding_key_does_not_retry() -> None:
    state = {k: v for k, v in _ELIGIBLE.items() if k != "_query_embedding"}
    assert rr.should_retry(state) is False


def test_kill_switch_disables_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVAL_RETRY_ENABLED", "false")
    assert rr.should_retry(_ELIGIBLE) is False


# ── graph routing ───────────────────────────────────────────────────────────

def test_route_goes_to_retry_when_eligible() -> None:
    assert _route_after_analyst_or_retry(_ELIGIBLE) == "retrieval_retry"


def test_route_unchanged_when_not_eligible() -> None:
    confident = {"needs_clarification": False, "retrieved_chunks": [_WEAK[0]]}
    assert _route_after_analyst_or_retry(confident) == "synthesiser"
    empty = {"needs_clarification": True, "retrieved_chunks": []}
    assert _route_after_analyst_or_retry(empty) == "clarification"


def test_graph_compiles_with_retry_node() -> None:
    compiled = build_graph().compile()
    assert "retrieval_retry" in compiled.get_graph().nodes


# ── the node ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_improves_confidence_and_caches_under_original_key() -> None:
    state = await _weak_state()
    assert state["needs_clarification"] is True
    before = state["confidence_score"]
    improved_before = _counter(retrieval_retry_total, outcome="improved")

    with (
        patch.object(rr, "retrieve_unscoped", AsyncMock(return_value=list(_STRONG))) as search,
        patch.object(rr.cache_svc, "set_cached_result", AsyncMock()) as set_cache,
    ):
        result = await rr.retrieval_retry_node(state)

    search.assert_awaited_once_with(_QUERY, _EMBEDDING)
    assert result["confidence_score"] > before
    assert result["confidence_score"] >= 0.6
    assert result["needs_clarification"] is False
    assert {c.id for c in result["retrieved_chunks"]} >= {"s1", "s2", "s3"}
    assert result["citations"], "improved result must carry real citations"
    assert _counter(retrieval_retry_total, outcome="improved") == improved_before + 1

    set_cache.assert_awaited_once()
    assert set_cache.await_args.args[0] == _cache_key(_QUERY, "bm", "government")


@pytest.mark.asyncio
async def test_retry_that_does_not_help_changes_nothing_and_does_not_cache() -> None:
    state = await _weak_state()
    other_weak = [_chunk("w3", similarity=0.1, gov=False), _chunk("w4", similarity=0.1, gov=False)]
    before = _counter(retrieval_retry_total, outcome="unchanged")

    with (
        patch.object(rr, "retrieve_unscoped", AsyncMock(return_value=other_weak)),
        patch.object(rr.cache_svc, "set_cached_result", AsyncMock()) as set_cache,
    ):
        result = await rr.retrieval_retry_node(state)

    assert result == {}
    set_cache.assert_not_awaited()
    assert _counter(retrieval_retry_total, outcome="unchanged") == before + 1


@pytest.mark.asyncio
async def test_retry_returning_only_chunks_already_held_is_unchanged() -> None:
    state = await _weak_state()
    before = _counter(retrieval_retry_total, outcome="unchanged")
    with patch.object(rr, "retrieve_unscoped", AsyncMock(return_value=list(_WEAK))):
        assert await rr.retrieval_retry_node(state) == {}
    assert _counter(retrieval_retry_total, outcome="unchanged") == before + 1


@pytest.mark.asyncio
async def test_retry_with_no_results_changes_nothing() -> None:
    state = await _weak_state()
    before = _counter(retrieval_retry_total, outcome="no_results")
    with patch.object(rr, "retrieve_unscoped", AsyncMock(return_value=[])):
        assert await rr.retrieval_retry_node(state) == {}
    assert _counter(retrieval_retry_total, outcome="no_results") == before + 1


@pytest.mark.asyncio
async def test_retry_search_failure_degrades_to_the_first_pass_result() -> None:
    state = await _weak_state()
    before = _counter(retrieval_retry_total, outcome="error")
    with patch.object(rr, "retrieve_unscoped", AsyncMock(side_effect=RuntimeError("db down"))):
        assert await rr.retrieval_retry_node(state) == {}
    assert _counter(retrieval_retry_total, outcome="error") == before + 1


@pytest.mark.asyncio
async def test_cache_write_failure_does_not_lose_the_improved_result() -> None:
    state = await _weak_state()
    with (
        patch.object(rr, "retrieve_unscoped", AsyncMock(return_value=list(_STRONG))),
        patch.object(rr.cache_svc, "set_cached_result", AsyncMock(side_effect=RuntimeError("redis down"))),
    ):
        result = await rr.retrieval_retry_node(state)
    assert result["needs_clarification"] is False


@pytest.mark.asyncio
async def test_retry_does_not_double_count_retrieval_score() -> None:
    """A retried query is observed once, by its first pass; the re-score must
    not add a second histogram sample."""
    state = await _weak_state()
    before = _hist_count(retrieval_score)
    with (
        patch.object(rr, "retrieve_unscoped", AsyncMock(return_value=list(_STRONG))),
        patch.object(rr.cache_svc, "set_cached_result", AsyncMock()),
    ):
        await rr.retrieval_retry_node(state)
    assert _hist_count(retrieval_score) == before


@pytest.mark.asyncio
async def test_retry_still_applies_the_same_clarification_bar() -> None:
    """Merged chunks are scored through the unchanged 0.6 threshold: a retry
    that only reaches 0.5 is an improvement but must still ask for
    clarification (the trust layer is not loosened)."""
    state = await _weak_state()
    middling = [  # 0.3 + 0.2 + 0.5*0.0 = 0.5 each, 3 of them
        _chunk("m1", similarity=0.0),
        _chunk("m2", similarity=0.0),
        _chunk("m3", similarity=0.0),
    ]
    with (
        patch.object(rr, "retrieve_unscoped", AsyncMock(return_value=middling)),
        patch.object(rr.cache_svc, "set_cached_result", AsyncMock()),
    ):
        result = await rr.retrieval_retry_node(state)
    assert 0.25 < result["confidence_score"] < 0.6
    assert result["needs_clarification"] is True


# ── retrieve_unscoped ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_unscoped_searches_all_domains_with_given_embedding() -> None:
    with (
        patch("app.agents.rag_node.hybrid_search", AsyncMock(return_value=list(_STRONG))) as search,
        patch("app.agents.rag_node.rerank_enabled", return_value=False),
    ):
        chunks = await retrieve_unscoped(_QUERY, _EMBEDDING)
    assert [c.id for c in chunks] == ["s1", "s2", "s3"]
    assert search.await_args.args == (_QUERY, _EMBEDDING)
    assert search.await_args.kwargs["domain"] is None


# ── analyst diagnostics (first pass only) ───────────────────────────────────

@pytest.mark.asyncio
async def test_first_pass_records_weak_relevance_cause() -> None:
    before = _counter(retrieval_low_confidence_total, cause="weak_relevance", domain_scoped="yes")
    await analyst_node({"query": _QUERY, "domain": "government", "retrieved_chunks": list(_WEAK)})
    assert _counter(retrieval_low_confidence_total, cause="weak_relevance", domain_scoped="yes") == before + 1


@pytest.mark.asyncio
async def test_first_pass_records_no_usable_chunks_cause_unscoped() -> None:
    before = _counter(retrieval_low_confidence_total, cause="no_usable_chunks", domain_scoped="no")
    await analyst_node({"query": _QUERY, "retrieved_chunks": []})
    assert _counter(retrieval_low_confidence_total, cause="no_usable_chunks", domain_scoped="no") == before + 1


@pytest.mark.asyncio
async def test_first_pass_records_too_few_supporting_cause() -> None:
    # One strong chunk: mean 0.95 clears 0.6, but only 1 corroborating chunk.
    before = _counter(retrieval_low_confidence_total, cause="too_few_supporting", domain_scoped="yes")
    result = await analyst_node({"query": _QUERY, "domain": "tax", "retrieved_chunks": [_STRONG[0]]})
    assert result["needs_clarification"] is True
    assert _counter(retrieval_low_confidence_total, cause="too_few_supporting", domain_scoped="yes") == before + 1


@pytest.mark.asyncio
async def test_confident_first_pass_records_no_cause() -> None:
    total_before = sum(
        _counter(retrieval_low_confidence_total, cause=c, domain_scoped=d)
        for c in ("no_usable_chunks", "weak_relevance", "too_few_supporting")
        for d in ("yes", "no")
    )
    result = await analyst_node({"query": _QUERY, "domain": "tax", "retrieved_chunks": list(_STRONG)})
    assert result["needs_clarification"] is False
    total_after = sum(
        _counter(retrieval_low_confidence_total, cause=c, domain_scoped=d)
        for c in ("no_usable_chunks", "weak_relevance", "too_few_supporting")
        for d in ("yes", "no")
    )
    assert total_after == total_before


@pytest.mark.asyncio
async def test_rescore_pass_records_nothing() -> None:
    before = _counter(retrieval_low_confidence_total, cause="weak_relevance", domain_scoped="yes")
    await analyse({"query": _QUERY, "domain": "government", "retrieved_chunks": list(_WEAK)}, first_pass=False)
    assert _counter(retrieval_low_confidence_total, cause="weak_relevance", domain_scoped="yes") == before
