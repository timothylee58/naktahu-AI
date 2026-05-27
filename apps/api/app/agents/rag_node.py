"""rag_node — Redis cache + ILMU embedding + Supabase hybrid search."""
from __future__ import annotations

import hashlib
import json

import structlog

from app.models.state import AgentState
from app.services import cache as cache_svc
from app.services.llm_client import (
    ILMU_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    ilmu_client,
    openai_client,
)
from app.services.vector_store import ChunkResult, hybrid_search

log = structlog.get_logger(__name__)

_CACHE_TTL = 3600


def _cache_key(query: str, language: str, domain: str) -> str:
    raw = f"{query.lower().strip()}|{language}|{domain}"
    return "cache:" + hashlib.sha256(raw.encode()).hexdigest()


def _serialize_chunks(chunks: list[ChunkResult]) -> list[dict]:
    return [
        {
            "id": c.id,
            "content": c.content,
            "source_title": c.source_title,
            "source_url": c.source_url,
            "ministry": c.ministry,
            "language": c.language,
            "similarity": c.similarity,
        }
        for c in chunks
    ]


def _deserialize_chunks(raw: list[dict]) -> list[ChunkResult]:
    return [
        ChunkResult(
            id=r["id"],
            content=r["content"],
            source_title=r["source_title"],
            source_url=r["source_url"],
            ministry=r["ministry"],
            language=r["language"],
            similarity=float(r["similarity"]),
        )
        for r in raw
    ]


async def _embed(query: str) -> list[float]:
    try:
        resp = await ilmu_client.embeddings.create(input=query, model=ILMU_EMBEDDING_MODEL)
        return resp.data[0].embedding
    except Exception as exc:
        if openai_client is None:
            raise RuntimeError("No embedding provider available") from exc
        log.warning("ilmu_embed_failed_using_openai", error=str(exc))
        resp = await openai_client.embeddings.create(input=query, model=OPENAI_EMBEDDING_MODEL)
        return resp.data[0].embedding


async def rag_node(state: AgentState) -> dict:
    """Check Redis cache, then fall through to hybrid search on miss."""
    query = state.get("query", "")
    language = state.get("language", "en")
    domain = state.get("domain", "government")

    key = _cache_key(query, language, domain)

    # Cache hit path
    cached = await cache_svc.get_cached_result(key)
    if cached is not None:
        log.info("rag_cache_hit", key=key[:16])
        return {"retrieved_chunks": _deserialize_chunks(cached)}

    # Cache miss — generate embedding and search
    log.info("rag_cache_miss", key=key[:16])
    embedding = await _embed(query)
    chunks = await hybrid_search(query, embedding, domain=domain, limit=5)

    # Persist to cache
    await cache_svc.set_cached_result(key, _serialize_chunks(chunks), ttl=_CACHE_TTL)

    return {"retrieved_chunks": chunks}
