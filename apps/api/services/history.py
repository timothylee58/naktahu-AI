"""Session history: Redis list (last 20) + Supabase user_sessions."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog
from redis.asyncio import Redis
from supabase import Client

logger = structlog.get_logger()

HISTORY_LIST_KEY = "session_history:{user_id}"
MAX_HISTORY = 20


def history_key(user_id: str) -> str:
    return HISTORY_LIST_KEY.format(user_id=user_id)


async def fetch_history_entries(redis_client: Redis, user_id: str) -> list[dict[str, Any]]:
    key = history_key(user_id)
    raw = await redis_client.lrange(key, 0, MAX_HISTORY - 1)
    out: list[dict[str, Any]] = []
    for item in raw:
        try:
            out.append(json.loads(item))
        except (json.JSONDecodeError, TypeError):
            logger.warning("history_decode_skip", key=key)
    return out


async def persist_session_entry(
    *,
    redis_client: Redis,
    supabase_client: Client,
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
    pipe = redis_client.pipeline(transaction=False)
    pipe.lpush(key, json.dumps(entry))
    pipe.ltrim(key, 0, MAX_HISTORY - 1)
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
        supabase_client.table("user_sessions").insert(row).execute()

    await asyncio.to_thread(_insert)
    logger.info("history_persisted", user_id=user_id, domain=domain)
