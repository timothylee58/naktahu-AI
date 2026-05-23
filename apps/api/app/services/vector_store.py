"""Supabase hybrid search — cosine similarity + BM25 via RPC."""
from __future__ import annotations

import os
from dataclasses import dataclass

from supabase import AsyncClient, acreate_client


@dataclass
class ChunkResult:
    id: str
    content: str
    source_title: str
    source_url: str
    ministry: str
    language: str
    similarity: float


async def _get_client() -> AsyncClient:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return await acreate_client(url, key)


async def hybrid_search(
    query: str,
    embedding: list[float],
    domain: str | None,
    limit: int = 5,
) -> list[ChunkResult]:
    """Call the hybrid_search Postgres RPC and return typed ChunkResult objects.

    Combines cosine similarity (weight 0.7) and BM25 rank (weight 0.3) as
    defined in migration 002_hybrid_search.sql.
    """
    client = await _get_client()
    params: dict = {
        "query_text": query,
        "query_embedding": embedding,
        "match_count": limit,
    }
    if domain is not None:
        params["domain_filter"] = domain

    resp = await client.rpc("hybrid_search", params).execute()

    results: list[ChunkResult] = []
    for row in (resp.data or []):
        results.append(
            ChunkResult(
                id=row["id"],
                content=row["content"],
                source_title=row["source_title"],
                source_url=row["source_url"],
                ministry=row["ministry"],
                language=row["language"],
                similarity=float(row["similarity"]),
            )
        )
    return results
