"""retrieval_retry_node — one bounded, deterministic retry after a weak analyst pass.

router_node can pick the wrong domain, and rag_node's hybrid search hard-filters
on it. rag_node already retries unscoped when the scoped search returns NOTHING;
this covers the case it misses, where the scoped search returns weak but
non-empty chunks and a better answer sits in another domain.

What it does: re-search with domain=None (reusing rag_node's embedding, so no
second embedding call), merge with the chunks already held, and re-score the
merged set through the SAME analyst thresholds. It keeps the result only if
confidence strictly improved.

What it deliberately does not do: rewrite the query (the analyst always scores
against the user's own query, so nothing can raise confidence by echoing the
chunks' wording), call an LLM, retry more than once, or touch the 0.6 bar.
Disable with RETRIEVAL_RETRY_ENABLED=false.
"""
from __future__ import annotations

import os
import time

import structlog
import weave

from app.agents.analyst_node import analyse
from app.agents.rag_node import _CACHE_TTL, _FINAL_CHUNK_COUNT, _cache_key, _serialize_chunks, retrieve_unscoped
from app.core.prometheus_metrics import (
    retrieval_retry_confidence_gain,
    retrieval_retry_seconds,
    retrieval_retry_total,
)
from app.models.state import AgentState
from app.services import cache as cache_svc
from app.services.vector_store import ChunkResult

log = structlog.get_logger(__name__)


def retry_enabled() -> bool:
    return os.environ.get("RETRIEVAL_RETRY_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


def should_retry(state: AgentState) -> bool:
    """Retry only when it can plausibly change the outcome and is cheap:

    - the analyst asked for clarification;
    - a domain filter was applied, so an unscoped search is actually different;
    - some chunks were retrieved (the empty case is rag_node's own fallback);
    - rag_node did a fresh search and left its embedding (a cache hit leaves
      none, which also stops a repeated query being retried on every request).
    """
    return (
        retry_enabled()
        and bool(state.get("needs_clarification", False))
        and state.get("domain") is not None
        and bool(state.get("retrieved_chunks"))
        and state.get("_query_embedding") is not None
    )


def _merge(held: list[ChunkResult], extra: list[ChunkResult]) -> list[ChunkResult]:
    by_id = {c.id: c for c in held}
    for c in extra:
        by_id.setdefault(c.id, c)
    return sorted(by_id.values(), key=lambda c: c.similarity, reverse=True)[:_FINAL_CHUNK_COUNT]


@weave.op()
async def retrieval_retry_node(state: AgentState) -> dict:
    t0 = time.monotonic()
    outcome = "error"
    try:
        held: list[ChunkResult] = state.get("retrieved_chunks", [])
        before = state.get("confidence_score", 0.0)
        try:
            extra = await retrieve_unscoped(state.get("query", ""), state["_query_embedding"])
        except Exception as exc:
            log.warning("retrieval_retry_search_failed", error=str(exc))
            return {}

        merged = _merge(held, extra)
        if not extra or {c.id for c in merged} == {c.id for c in held}:
            outcome = "no_results" if not extra else "unchanged"
            return {}

        result = await analyse({**state, "retrieved_chunks": merged}, first_pass=False)
        after = result.get("confidence_score", 0.0)
        if after <= before:
            outcome = "unchanged"
            return {}

        outcome = "improved"
        retrieval_retry_confidence_gain.observe(after - before)
        log.info(
            "retrieval_retry_improved",
            domain=state.get("domain"),
            before=round(before, 4),
            after=round(after, 4),
            still_needs_clarification=result.get("needs_clarification"),
        )
        # Cache the better set under the ORIGINAL key so a repeat of this query
        # gets it directly instead of the weak scoped result.
        try:
            key = _cache_key(state.get("query", ""), state.get("language", "en"), state.get("domain"))
            await cache_svc.set_cached_result(key, _serialize_chunks(result["retrieved_chunks"]), ttl=_CACHE_TTL)
        except Exception as exc:
            log.warning("retrieval_retry_cache_write_failed", error=str(exc))
        return result
    finally:
        elapsed = time.monotonic() - t0
        retrieval_retry_total.labels(outcome=outcome).inc()
        retrieval_retry_seconds.observe(elapsed)
        # Logged as well as counted: the Prometheus registry is per-process and
        # production runs 2 workers, so these log lines are the dependable
        # source for frequency and cost.
        log.info("retrieval_retry_done", outcome=outcome, duration_ms=round(elapsed * 1000))
