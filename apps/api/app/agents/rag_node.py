"""rag_node — Redis cache + dual-embedding hybrid search (ILMU first, OpenAI fallback).

See llm_client.py's dual-embedding invariant: ILMU vectors are only ever
searched via hybrid_search_ilmu, OpenAI vectors only via hybrid_search.
"""
from __future__ import annotations

import hashlib

import structlog
import weave

from app.models.state import AgentState
from app.services import cache as cache_svc
from app.services.llm_client import (
    ILMU_EMBEDDING_DIMS,
    ILMU_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    ilmu_client,
    openai_client,
)
from app.services.reranker import rerank_chunks, rerank_enabled
from app.services.vector_store import (
    ChunkResult,
    hybrid_search,
    hybrid_search_ilmu,
    hybrid_search_madani_schemes,
)

log = structlog.get_logger(__name__)

_CACHE_TTL = 3600
_FINAL_CHUNK_COUNT = 5
# Wider than _FINAL_CHUNK_COUNT only when reranking is on — the reranker
# needs a real pool to choose from; when it's off, requesting the wider
# pool from hybrid_search would just waste DB work for chunks nothing
# reads, so this only takes effect behind the RERANK_ENABLED flag below.
_RERANK_CANDIDATE_POOL = 12


def _cache_key(query: str, language: str, domain: str | None) -> str:
    raw = f"{query.lower().strip()}|{language}|{domain or '_any'}"
    return "cache:" + hashlib.sha256(raw.encode()).hexdigest()


def _serialize_chunks(chunks: list[ChunkResult]) -> list[dict]:
    # Persist every ChunkResult field. Dropping the freshness columns here
    # (effective_date/superseded_by/expiry_aware/source_date) silently disables
    # analyst_node's staleness + superseded-chunk checks on every cache hit, so
    # a superseded or stale chunk would be cited unchecked once cached.
    return [
        {
            "id": c.id,
            "content": c.content,
            "source_title": c.source_title,
            "source_url": c.source_url,
            "ministry": c.ministry,
            "language": c.language,
            "similarity": c.similarity,
            "expiry_aware": c.expiry_aware,
            "source_date": c.source_date,
            "effective_date": c.effective_date,
            "superseded_by": c.superseded_by,
        }
        for c in chunks
    ]


def _deserialize_chunks(raw: list[dict]) -> list[ChunkResult]:
    # .get() with defaults keeps older cache entries (written before the
    # freshness columns existed) readable instead of raising KeyError.
    return [
        ChunkResult(
            id=r["id"],
            content=r["content"],
            source_title=r["source_title"],
            source_url=r["source_url"],
            ministry=r["ministry"],
            language=r["language"],
            similarity=float(r["similarity"]),
            expiry_aware=bool(r.get("expiry_aware", False)),
            source_date=r.get("source_date"),
            effective_date=r.get("effective_date"),
            superseded_by=r.get("superseded_by"),
        )
        for r in raw
    ]


async def _embed(query: str) -> list[float]:
    """Embed for document_chunks.embedding — OpenAI OPENAI_EMBEDDING_MODEL, 1536-dim.

    This is the model the live corpus was built with, so it's the one every
    non-ILMU search path and every write to the `embedding` column must use.
    Also imported by router_node (speculative embed), tools.py,
    grant_rag_node, scripts/ingest_feed.py, madani_scheme_ingest and
    upload_parliament — this is the single definition for that column.

    No cross-provider fallback inside: raising is the safe path. A failure
    here surfaces as retrieved_chunks=[] -> needs_clarification, never as
    results compared across two embedding spaces.
    """
    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY is not set — cannot embed for document_chunks.embedding")
    resp = await openai_client.embeddings.create(input=query, model=OPENAI_EMBEDDING_MODEL)
    return resp.data[0].embedding


async def _embed_ilmu(query: str) -> list[float]:
    """Embed for document_chunks.embedding_ilmu — ILMU_EMBEDDING_MODEL, 4096-dim.

    Only ever paired with hybrid_search_ilmu (reads) and the embedding_ilmu
    column (writes). The dimension check turns a wrong ILMU_EMBEDDING_MODEL
    into a clear error instead of a Postgres vector-type failure.
    """
    resp = await ilmu_client.embeddings.create(input=query, model=ILMU_EMBEDDING_MODEL)
    embedding = resp.data[0].embedding
    if len(embedding) != ILMU_EMBEDDING_DIMS:
        raise ValueError(
            f"ILMU embedding has {len(embedding)} dims, expected {ILMU_EMBEDDING_DIMS} "
            f"(model={ILMU_EMBEDDING_MODEL!r}) — check ILMU_EMBEDDING_MODEL"
        )
    return embedding


async def _search_with_domain_fallback(search_fn, query: str, embedding: list[float], domain: str | None, limit: int) -> list[ChunkResult]:
    """Run one search; if a domain-scoped search is empty, retry unfiltered.

    Recall fallback: the search functions hard-filter on dc.domain, so a
    single misclassified domain from router_node (e.g. a tax question tagged
    "government") would return zero chunks. Retrying unfiltered lets relevant
    chunks in another domain still surface, ranked by similarity.
    """
    chunks = await search_fn(query, embedding, domain=domain, limit=limit)
    if not chunks and domain is not None:
        log.info("rag_domain_fallback", domain=domain)
        chunks = await search_fn(query, embedding, domain=None, limit=limit)
    return chunks


@weave.op()
async def rag_node(state: AgentState) -> dict:
    """Check Redis cache; on miss, search ILMU vectors first, then OpenAI vectors."""
    query = state.get("query", "")
    language = state.get("language", "en")
    # None (not "government") when unclassified — see app/models/state.py's
    # domain field docstring for why a specific-domain default is a trap.
    domain = state.get("domain")
    speculative_task = state.get("_speculative_embedding_task")

    key = _cache_key(query, language, domain)

    # Cache hit path
    cached = await cache_svc.get_cached_result(key)
    if cached is not None:
        log.info("rag_cache_hit", key=key[:16])
        # router_node only ever starts this task when has_query_been_seen()
        # was False, which should make a same-query cache hit here
        # impossible in the common case — but a same-query race or a
        # domain/language reclassification on a repeat query can still land
        # here with a task in flight. Cancel it rather than let it run unused.
        if speculative_task is not None and not speculative_task.done():
            speculative_task.cancel()
        return {"retrieved_chunks": _deserialize_chunks(cached)}

    log.info("rag_cache_miss", key=key[:16])
    do_rerank = rerank_enabled()
    search_limit = _RERANK_CANDIDATE_POOL if do_rerank else _FINAL_CHUNK_COUNT

    # router_node's speculative task (if any) embeds with OpenAI (_embed), so
    # it's only useful for the OpenAI path. Await it at most once.
    openai_embedding: list[float] | None = None

    async def _openai_embedding() -> list[float]:
        nonlocal openai_embedding, speculative_task
        if openai_embedding is None:
            if speculative_task is not None:
                task, speculative_task = speculative_task, None
                openai_embedding = await task
            else:
                openai_embedding = await _embed(query)
        return openai_embedding

    try:
        # 1. ILMU first (user decision, 2026-09-23). Any failure — embed error,
        #    wrong model, migration 051 not applied — or an empty result (rows
        #    not yet backfilled) falls through to OpenAI rather than failing
        #    the query.
        chunks: list[ChunkResult] = []
        provider = "ilmu"
        try:
            ilmu_embedding = await _embed_ilmu(query)
            chunks = await _search_with_domain_fallback(hybrid_search_ilmu, query, ilmu_embedding, domain, search_limit)
            if not chunks:
                log.info("rag_ilmu_empty_falling_back_to_openai")
        except Exception as exc:
            log.warning("rag_ilmu_failed_falling_back_to_openai", error=str(exc))
            chunks = []

        # 2. OpenAI fallback over the `embedding` column.
        if not chunks:
            provider = "openai"
            chunks = await _search_with_domain_fallback(hybrid_search, query, await _openai_embedding(), domain, search_limit)

        # Additive, welfare-only: merge in madani_scheme's own semantic search
        # (migration 038's RPC). madani_scheme is embedded with the OpenAI
        # model (via _embed), so it's always queried with the OpenAI vector
        # regardless of which provider served document_chunks. Own try/except
        # so a failure here degrades to "just the document_chunks results".
        if domain == "welfare":
            try:
                scheme_chunks = await hybrid_search_madani_schemes(query, await _openai_embedding(), limit=search_limit)
                chunks = chunks + scheme_chunks
            except Exception as exc:
                log.warning("rag_madani_scheme_search_failed", error=str(exc))

        log.info("rag_retrieval_provider", provider=provider, chunks=len(chunks))

        if do_rerank and chunks:
            chunks = await rerank_chunks(query=query, chunks=chunks, top_n=_FINAL_CHUNK_COUNT)
        else:
            chunks = chunks[:_FINAL_CHUNK_COUNT]
    except Exception as exc:
        log.warning("rag_retrieval_failed", error=str(exc))
        return {"retrieved_chunks": []}
    finally:
        # ILMU served the query and the speculative OpenAI embed was never
        # needed — cancel it instead of leaving it running unawaited.
        if speculative_task is not None and not speculative_task.done():
            speculative_task.cancel()

    # Persist to cache, and record that this query text has now been cached
    # (see cache.mark_query_seen's docstring) so a future router_node run
    # knows it's safe to fire a speculative embed for a repeat of this query.
    await cache_svc.set_cached_result(key, _serialize_chunks(chunks), ttl=_CACHE_TTL)
    await cache_svc.mark_query_seen(query, ttl=_CACHE_TTL)

    return {"retrieved_chunks": chunks}
