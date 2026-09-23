"""rag_node — Redis cache + corpus embedding (ILMU gateway first, OpenAI fallback) + Supabase hybrid search."""
from __future__ import annotations

import hashlib

import structlog
import weave

from app.models.state import AgentState
from app.services import cache as cache_svc
from app.services.llm_client import (
    EMBEDDING_DIMS,
    ILMU_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    embedding_routes_share_a_model,
    ilmu_client,
    openai_client,
)
from app.services.reranker import rerank_chunks, rerank_enabled
from app.services.vector_store import ChunkResult, hybrid_search, hybrid_search_madani_schemes

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


def _checked(embedding: list[float], route: str) -> list[float]:
    if len(embedding) != EMBEDDING_DIMS:
        raise ValueError(f"{route} embedding has {len(embedding)} dims, expected {EMBEDDING_DIMS}")
    return embedding


async def _embed(query: str) -> list[float]:
    """Embed with the corpus's model (text-embedding-3-small), ILMU gateway first.

    Tries ILMU's route to the model, then OpenAI direct. Falling back is safe
    only because both routes serve the SAME model — see llm_client.py. If
    ILMU_EMBEDDING_MODEL names a different model, the ILMU route is skipped
    entirely rather than mixing vector spaces.

    Raises when no route works. That's the safe path and is already handled:
    rag_node returns retrieved_chunks=[], analyst_node sets needs_clarification,
    and the user is asked to rephrase instead of shown sourced-looking noise.
    Also imported by router_node (speculative embed), tools, grant_rag_node,
    scripts/ingest_feed.py, madani_scheme_ingest and upload_parliament, so this
    is the single definition of the corpus embedding for reads AND writes.
    """
    errors: list[str] = []
    if embedding_routes_share_a_model(ILMU_EMBEDDING_MODEL, OPENAI_EMBEDDING_MODEL):
        try:
            resp = await ilmu_client.embeddings.create(input=query, model=ILMU_EMBEDDING_MODEL)
            return _checked(resp.data[0].embedding, "ILMU")
        except Exception as exc:
            errors.append(f"ilmu: {exc}")
            log.warning("embed_ilmu_failed_falling_back_to_openai", error=str(exc))
    else:
        errors.append(f"ilmu: skipped, {ILMU_EMBEDDING_MODEL!r} is not the corpus model {OPENAI_EMBEDDING_MODEL!r}")
        log.error("embed_ilmu_model_mismatch_skipped", ilmu_model=ILMU_EMBEDDING_MODEL, corpus_model=OPENAI_EMBEDDING_MODEL)

    if openai_client is not None:
        resp = await openai_client.embeddings.create(input=query, model=OPENAI_EMBEDDING_MODEL)
        return _checked(resp.data[0].embedding, "OpenAI")
    errors.append("openai: OPENAI_API_KEY not set")
    raise RuntimeError("No embedding route available — " + "; ".join(errors))


@weave.op()
async def rag_node(state: AgentState) -> dict:
    """Check Redis cache, then fall through to hybrid search on miss."""
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
        # impossible in the common case — but a same-query race (two
        # concurrent requests for a brand-new query) or a domain/language
        # reclassification on a repeat query can still land here with a
        # task in flight. Cancel it rather than let it run to completion
        # unused.
        if speculative_task is not None and not speculative_task.done():
            speculative_task.cancel()
        return {"retrieved_chunks": _deserialize_chunks(cached)}

    # Cache miss — generate embedding (reusing router_node's speculative
    # task if one is in flight — see AgentState._speculative_embedding_task
    # and cache.has_query_been_seen's docstring) and search
    log.info("rag_cache_miss", key=key[:16])
    do_rerank = rerank_enabled()
    search_limit = _RERANK_CANDIDATE_POOL if do_rerank else _FINAL_CHUNK_COUNT
    try:
        embedding = await speculative_task if speculative_task is not None else await _embed(query)
        chunks = await hybrid_search(query, embedding, domain=domain, limit=search_limit)
        # Recall fallback: hybrid_search hard-filters on dc.domain = domain_filter,
        # so a single misclassified domain from router_node (e.g. a tax question
        # tagged "government") returns zero chunks — the user then sees a
        # clarification prompt with no sources at all. When a domain-scoped search
        # comes back empty, retry once unfiltered so relevant chunks in another
        # domain can still surface and be ranked by vector similarity.
        if not chunks and domain is not None:
            log.info("rag_domain_fallback", domain=domain)
            chunks = await hybrid_search(query, embedding, domain=None, limit=search_limit)

        # Additive, welfare-only: merge in madani_scheme's own semantic
        # search (migration 038's dedicated RPC) alongside whatever
        # document_chunks already found for this domain. Its own try/except
        # (not the outer one) so a failure here — e.g. migration 038 not yet
        # applied, or the still-empty table — degrades to "just the
        # document_chunks results," never aborts retrieval for the whole
        # query the way letting this exception hit the outer handler would.
        if domain == "welfare":
            try:
                scheme_chunks = await hybrid_search_madani_schemes(query, embedding, limit=search_limit)
                chunks = chunks + scheme_chunks
            except Exception as exc:
                log.warning("rag_madani_scheme_search_failed", error=str(exc))

        if do_rerank and chunks:
            chunks = await rerank_chunks(query=query, chunks=chunks, top_n=_FINAL_CHUNK_COUNT)
        else:
            chunks = chunks[:_FINAL_CHUNK_COUNT]
    except Exception as exc:
        log.warning("rag_retrieval_failed", error=str(exc))
        return {"retrieved_chunks": []}

    # Persist to cache, and record that this query text has now been
    # cached (domain/language-agnostic marker — see cache.mark_query_seen's
    # docstring) so a future router_node run knows it's safe to fire a
    # speculative embed for a repeat of this exact query text.
    await cache_svc.set_cached_result(key, _serialize_chunks(chunks), ttl=_CACHE_TTL)
    await cache_svc.mark_query_seen(query, ttl=_CACHE_TTL)

    return {"retrieved_chunks": chunks}
