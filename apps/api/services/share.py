"""Shareable answer permalinks.

Persists a full Q&A (query, complete answer, citations) under a random UUID
that doubles as the public share id. Reads are intentionally open — see
015_shared_answers.sql — since the whole point is a link anyone can open.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog
from supabase import Client

logger = structlog.get_logger()


async def create_shared_answer(
    *,
    supabase_client: Client,
    user_id: Optional[str],
    query: str,
    response_text: str,
    citations: list[Any],
    domain: str,
    language: str,
    confidence: Optional[float],
) -> str:
    """Persist the shared answer and return its id (used as /a/{id})."""
    row = {
        "user_id": user_id,
        "query": query,
        "response_text": response_text,
        "citations": citations,
        "domain": domain,
        "language": language,
        "confidence": confidence,
    }

    def _insert() -> str:
        res = supabase_client.table("shared_answers").insert(row).execute()
        return res.data[0]["id"]

    share_id = await asyncio.to_thread(_insert)
    logger.info("shared_answer_created", share_id=share_id, domain=domain)
    return share_id


async def get_shared_answer(
    supabase_client: Client, share_id: str
) -> Optional[dict[str, Any]]:
    def _fetch() -> Optional[dict[str, Any]]:
        res = (
            supabase_client.table("shared_answers")
            .select("*")
            .eq("id", share_id)
            .execute()
        )
        return res.data[0] if res.data else None

    return await asyncio.to_thread(_fetch)
