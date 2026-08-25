"""Async Redis helpers for query caching and session history."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional

import redis.asyncio as aioredis
import structlog

log = structlog.get_logger(__name__)

_client: Optional[aioredis.Redis] = None  # type: ignore[type-arg]


def _get_client() -> aioredis.Redis:  # type: ignore[type-arg]
    global _client
    if _client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        _client = aioredis.from_url(url, decode_responses=True)
    return _client


async def get_cached_result(key: str) -> Optional[Any]:
    """Return deserialized cached value or None on miss."""
    try:
        raw = await _get_client().get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        log.warning("cache_get_error", key=key, error=str(exc))
        return None


async def set_cached_result(key: str, value: Any, ttl: int = 3600) -> None:
    """Serialize and store a value with TTL seconds."""
    try:
        await _get_client().setex(key, ttl, json.dumps(value))
    except Exception as exc:
        log.warning("cache_set_error", key=key, error=str(exc))


def _seen_key(query: str) -> str:
    # Deliberately domain/language-agnostic (unlike rag_node._cache_key,
    # which includes both) — this answers "has this exact query text ever
    # been cached under ANY domain/language", not "is this specific
    # domain+language combo cached". See router_node's use of this: an
    # absent marker guarantees the real, domain-scoped cache lookup will
    # also miss (the marker is only ever set alongside a real cache
    # write), which is what makes it safe to fire a speculative embedding
    # call whenever the marker is absent — it's never wasted.
    return "cache:seen:" + hashlib.sha256(query.lower().strip().encode()).hexdigest()


async def mark_query_seen(query: str, ttl: int = 3600) -> None:
    """Records that `query` has been cached (under whatever domain/language
    it was classified as this time) — see _seen_key's docstring. Same TTL
    as the real cache entry, so the marker never outlives what it's
    describing."""
    try:
        await _get_client().setex(_seen_key(query), ttl, "1")
    except Exception as exc:
        log.warning("cache_mark_seen_error", error=str(exc))


async def has_query_been_seen(query: str) -> bool:
    """True only if `query` has been cached before, under any
    domain/language. Fails closed to False on a Redis error — the
    speculative-embed caller degrades to "don't speculate" rather than
    risk treating a check failure as a green light."""
    try:
        return bool(await _get_client().exists(_seen_key(query)))
    except Exception as exc:
        log.warning("cache_has_seen_error", error=str(exc))
        return False


async def get_session_history(user_id: str) -> list[dict]:
    """Return up to 50 most-recent session history entries for a user."""
    try:
        raw_list = await _get_client().lrange(f"session:{user_id}:history", 0, 49)
        return [json.loads(item) for item in raw_list]
    except Exception as exc:
        log.warning("session_history_get_error", user_id=user_id, error=str(exc))
        return []


async def append_session_history(user_id: str, entry: dict) -> None:
    """Prepend an entry to the user's session history list (capped at 50)."""
    key = f"session:{user_id}:history"
    try:
        pipe = _get_client().pipeline()
        pipe.lpush(key, json.dumps(entry))
        pipe.ltrim(key, 0, 49)
        pipe.expire(key, 2592000)  # 30 days
        await pipe.execute()
    except Exception as exc:
        log.warning("session_history_append_error", user_id=user_id, error=str(exc))


async def ping() -> bool:
    """Return True if Redis is reachable."""
    try:
        return await _get_client().ping()  # type: ignore[return-value]
    except Exception:
        return False
