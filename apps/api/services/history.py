"""Session history: Redis list (last 20) + Supabase user_sessions."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any

import structlog
from redis.asyncio import Redis
from supabase import Client

logger = structlog.get_logger()

HISTORY_LIST_KEY = "session_history:{user_id}"
MAX_HISTORY = 20
# Matches the persisted-write TTL below — a Redis-only cap on how long the
# fast-path cache is trusted; Supabase (user_sessions) is the durable store.
HISTORY_TTL_SECONDS = 30 * 24 * 60 * 60


def history_key(user_id: str) -> str:
    return HISTORY_LIST_KEY.format(user_id=user_id)


async def _fetch_history_from_supabase(
    supabase_client: Client | None, user_id: str
) -> list[dict[str, Any]]:
    """Durable fallback for fetch_history_entries.

    Redis is a fast-path cache with no persistence guarantee — a Railway
    Redis restart, redeploy, or eviction under memory pressure empties it
    without warning, and reads that trust an empty Redis list as "no
    history" silently lose a registered user's history even though every
    write already lands in user_sessions (003_user_sessions.sql exists
    specifically to be that source of truth).
    """
    if supabase_client is None:
        logger.warning("history_supabase_unavailable")
        return []
    try:
        res = await asyncio.to_thread(
            lambda: supabase_client.table("user_sessions")
            .select("query,language,domain,response_summary,citations,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(MAX_HISTORY)
            .execute()
        )
    except Exception as exc:
        logger.warning("history_supabase_fetch_failed", error=str(exc))
        return []

    out: list[dict[str, Any]] = []
    for row in res.data or []:
        created_at = row.get("created_at")
        ts = None
        if created_at:
            try:
                ts = int(datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp())
            except ValueError:
                ts = None
        out.append(
            {
                "query": row.get("query"),
                "language": row.get("language"),
                "domain": row.get("domain"),
                "response_summary": row.get("response_summary"),
                "citations": row.get("citations") or [],
                "ts": ts,
            }
        )
    return out


async def fetch_history_entries(
    redis_client: Redis | None, supabase_client: Client | None, user_id: str
) -> list[dict[str, Any]]:
    if redis_client is not None:
        key = history_key(user_id)
        raw = await redis_client.lrange(key, 0, MAX_HISTORY - 1)
        out: list[dict[str, Any]] = []
        for item in raw:
            try:
                out.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                logger.warning("history_decode_skip", key=key)
        if out:
            return out
        logger.info("history_redis_empty_falling_back_to_supabase", user_id=user_id)
    else:
        logger.warning("history_redis_unavailable")

    # Redis had nothing (cold cache, eviction, or genuinely no history yet) —
    # Supabase is authoritative either way, so always confirm against it
    # rather than trusting an empty Redis read as "no history".
    return await _fetch_history_from_supabase(supabase_client, user_id)


async def persist_session_entry(
    *,
    redis_client: Redis | None,
    supabase_client: Client | None,
    user_id: str,
    query: str,
    language: str,
    domain: str,
    response_text: str,
    citations: list[Any],
) -> None:
    response_summary = response_text[:150]
    entry = {
        "query": query,
        "language": language,
        "domain": domain,
        "response_summary": response_summary,
        "citations": citations,
        "ts": int(time.time()),
    }
    key = history_key(user_id)
    if redis_client is not None:
        pipe = redis_client.pipeline(transaction=False)
        pipe.lpush(key, json.dumps(entry))
        pipe.ltrim(key, 0, MAX_HISTORY - 1)
        pipe.expire(key, HISTORY_TTL_SECONDS)
        await pipe.execute()

    row = {
        "user_id": user_id,
        "query": query,
        "language": language,
        "domain": domain,
        "response_summary": response_summary,
        "citations": citations,
    }

    def _insert() -> None:
        if supabase_client is None:
            return
        supabase_client.table("user_sessions").insert(row).execute()

    if supabase_client is not None:
        await asyncio.to_thread(_insert)
    logger.info("history_persisted", user_id=user_id, domain=domain)
