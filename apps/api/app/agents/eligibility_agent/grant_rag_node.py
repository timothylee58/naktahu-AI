"""grant_rag_node — Redis-cache-first structured + vector retrieval of grants.

Queries the structured `grant_database` table (filterable by sector, active
status, and company-age minimum) alongside a pgvector hybrid search over
`document_chunks` for supporting narrative context. Follows the same
cache-key discipline as app/agents/rag_node.py (CLAUDE.md hard rule):
sha256(query.lower().strip() + "|" + language + "|" + domain).

Takes `supabase` explicitly (rather than reading it off state) so it is
trivially unit-testable with a mocked client; graph.py's node wrapper
threads it through from state["_supabase"].
"""
from __future__ import annotations

import hashlib
from typing import Any

import structlog

from app.agents.eligibility_agent.state import EligibilityState
from app.services.cache import get_cached_result, set_cached_result
from app.services.llm_client import ILMU_EMBEDDING_MODEL, OPENAI_EMBEDDING_MODEL, ilmu_client, openai_client

log = structlog.get_logger(__name__)

_CACHE_TTL = 3600
_DOMAIN = "government"


def _cache_key(query: str, language: str, domain: str) -> str:
    raw = f"{query.lower().strip()}|{language}|{domain}"
    return "cache:eligibility:" + hashlib.sha256(raw.encode()).hexdigest()


async def _embed_query(query: str) -> list[float]:
    try:
        resp = await ilmu_client.embeddings.create(input=query, model=ILMU_EMBEDDING_MODEL)
        return resp.data[0].embedding
    except Exception as exc:
        if openai_client is None:
            raise RuntimeError("No embedding provider available") from exc
        log.warning("ilmu_embed_failed_using_openai", error=str(exc))
        resp = await openai_client.embeddings.create(input=query, model=OPENAI_EMBEDDING_MODEL)
        return resp.data[0].embedding


async def grant_rag_node(state: EligibilityState, supabase: Any) -> dict[str, Any]:
    profile = state.get("business_profile")
    if not profile:
        return {"structured_grants": [], "retrieved_grant_chunks": []}

    language = state.get("language") or "en"
    sector = profile.get("sector", "")
    query = f"government grants {sector} {profile.get('business_type', '')} Malaysia 2026"
    key = _cache_key(query, language, sector or "_any")

    cached = await get_cached_result(key)
    if cached is not None:
        log.info("grant_rag_cache_hit", key=key[:24])
        return {
            "structured_grants": cached.get("structured", []),
            "retrieved_grant_chunks": cached.get("chunks", []),
        }

    log.info("grant_rag_cache_miss", key=key[:24])

    try:
        table_res = await (
            supabase.table("grant_database")
            .select("*")
            .eq("is_active", True)
            .or_(f"eligible_sectors.cs.{{{sector}}},eligible_sectors.cs.{{all}}")
            .lte("company_age_min_months", profile.get("registered_months", 0))
            .execute()
        )
        structured = table_res.data or []
    except Exception as exc:
        log.warning("grant_database_query_failed", error=str(exc))
        structured = []

    chunks: list[dict[str, Any]] = []
    try:
        embedding = await _embed_query(query)
        rpc_res = await supabase.rpc(
            "match_document_chunks",
            {"query_embedding": embedding, "match_domain": _DOMAIN, "match_count": 8},
        ).execute()
        chunks = rpc_res.data or []
    except Exception as exc:
        log.warning("grant_chunk_rpc_failed", error=str(exc))
        chunks = []

    await set_cached_result(key, {"structured": structured, "chunks": chunks}, ttl=_CACHE_TTL)

    return {"structured_grants": structured, "retrieved_grant_chunks": chunks}
