"""Session history: Redis list (last 20) + Supabase user_sessions."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
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
            .select(
                "id,title,query,language,domain,response_summary,response_text,"
                "confidence,suggestions,agency_contact,citations,created_at"
            )
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
                # Falls back to None on rows written before migration 029 —
                # the frontend hides rename/delete for entries with no id.
                "id": row.get("id"),
                "title": row.get("title"),
                "query": row.get("query"),
                "language": row.get("language"),
                "domain": row.get("domain"),
                "response_summary": row.get("response_summary"),
                # Falls back to None on rows written before migration 028 —
                # the frontend re-prompts for those instead of reconstructing.
                "response_text": row.get("response_text"),
                "confidence": row.get("confidence"),
                "suggestions": row.get("suggestions") or [],
                "agency_contact": row.get("agency_contact"),
                "citations": row.get("citations") or [],
                "ts": ts,
            }
        )
    return out


async def fetch_history_entries(
    redis_client: Redis | None, supabase_client: Client | None, user_id: str
) -> list[dict[str, Any]]:
    key = history_key(user_id)
    if redis_client is not None:
        try:
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
        except Exception as exc:
            # A live Redis outage (not just a cold/missing key) must not 500
            # the route — that would defeat the whole point of the fallback.
            logger.warning("history_redis_query_failed", error=str(exc))
    else:
        logger.warning("history_redis_unavailable")

    # Redis had nothing (cold cache, eviction, outage, or genuinely no
    # history yet) — Supabase is authoritative either way, so always confirm
    # against it rather than trusting an empty Redis read as "no history".
    entries = await _fetch_history_from_supabase(supabase_client, user_id)

    if entries and redis_client is not None:
        # Warm the cache so the next read for this user hits the fast path
        # instead of Supabase again. Supabase returns newest-first, and
        # rpush appends in the order given, so pushing newest-first onto an
        # empty list reproduces the same index-0-is-newest layout lpush
        # normally builds one entry at a time.
        try:
            pipe = redis_client.pipeline(transaction=False)
            pipe.rpush(key, *[json.dumps(e) for e in entries])
            pipe.expire(key, HISTORY_TTL_SECONDS)
            await pipe.execute()
        except Exception as exc:
            logger.warning("history_redis_warm_failed", error=str(exc))

    return entries


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
    confidence: float | None = None,
    suggestions: list[str] | None = None,
    agency_contact: dict[str, Any] | None = None,
) -> None:
    response_summary = response_text[:150]
    suggestions = suggestions or []
    entry_id = str(uuid.uuid4())
    entry = {
        "id": entry_id,
        "title": None,
        "query": query,
        "language": language,
        "domain": domain,
        "response_summary": response_summary,
        "response_text": response_text,
        "confidence": confidence,
        "suggestions": suggestions,
        "agency_contact": agency_contact,
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
        "id": entry_id,
        "user_id": user_id,
        "query": query,
        "language": language,
        "domain": domain,
        "response_summary": response_summary,
        "response_text": response_text,
        "confidence": confidence,
        "suggestions": suggestions,
        "agency_contact": agency_contact,
        "citations": citations,
    }

    def _insert() -> None:
        if supabase_client is None:
            return
        supabase_client.table("user_sessions").insert(row).execute()

    if supabase_client is not None:
        try:
            await asyncio.to_thread(_insert)
        except Exception as exc:
            # Degrade gracefully if migration 028 hasn't been applied yet
            # (missing response_text/confidence/suggestions/agency_contact
            # columns) rather than crashing the request — Redis already has
            # the entry, so history isn't fully lost, just not durable yet.
            logger.warning("history_supabase_insert_failed", error=str(exc), user_id=user_id)
    logger.info("history_persisted", user_id=user_id, domain=domain)


async def _invalidate_redis_cache(redis_client: Redis | None, user_id: str) -> None:
    """Drop the Redis list after a mutation instead of surgically patching it.

    Entries are plain JSON strings with no indexed lookup by id, so patching
    the list in place means fetch-all/filter/rewrite anyway. Simplest correct
    option: delete the key — fetch_history_entries already treats Supabase as
    authoritative and rewarms the cache on the next read.
    """
    if redis_client is None:
        return
    try:
        await redis_client.delete(history_key(user_id))
    except Exception as exc:
        logger.warning("history_redis_invalidate_failed", error=str(exc), user_id=user_id)


async def delete_session_entry(
    *,
    redis_client: Redis | None,
    supabase_client: Client | None,
    user_id: str,
    entry_id: str,
) -> bool:
    """Delete one history entry. Returns False if it didn't exist / wasn't owned by user_id."""
    if supabase_client is None:
        return False

    def _delete() -> list[dict[str, Any]]:
        res = (
            supabase_client.table("user_sessions")
            .delete()
            .eq("id", entry_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data or []

    try:
        deleted = await asyncio.to_thread(_delete)
    except Exception as exc:
        logger.warning("history_delete_failed", error=str(exc), user_id=user_id, entry_id=entry_id)
        return False
    if deleted:
        await _invalidate_redis_cache(redis_client, user_id)
    return bool(deleted)


async def rename_session_entry(
    *,
    redis_client: Redis | None,
    supabase_client: Client | None,
    user_id: str,
    entry_id: str,
    title: str,
) -> bool:
    """Set a custom display title for one history entry. Returns False if it didn't exist / wasn't owned by user_id."""
    if supabase_client is None:
        return False

    def _update() -> list[dict[str, Any]]:
        res = (
            supabase_client.table("user_sessions")
            .update({"title": title})
            .eq("id", entry_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data or []

    try:
        updated = await asyncio.to_thread(_update)
    except Exception as exc:
        logger.warning("history_rename_failed", error=str(exc), user_id=user_id, entry_id=entry_id)
        return False
    if updated:
        await _invalidate_redis_cache(redis_client, user_id)
    return bool(updated)


async def fetch_agent_run_history(
    *,
    supabase_client: Client | None,
    user_id: str,
    agent_name: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Real, previously-logged vertical-agent runs (agent_runner.py's
    _log_run() already writes every start/continue call to `agent_runs` —
    this is the first read path for that table). Distinct from the
    query/chat history above: this is structured agent output (drafts,
    checklists, eligibility results), not a Q&A transcript, so it's a
    separate table and a separate fetch rather than folded into
    fetch_history_entries().

    No Redis cache layer — agent_runs is already the durable source with
    no separate fast-path cache to keep in sync, and this is a low-volume
    read (one user's own history page), unlike the chat-history endpoint's
    higher read/write ratio.
    """
    if supabase_client is None:
        logger.warning("agent_run_history_supabase_unavailable")
        return []

    def _fetch() -> list[dict[str, Any]]:
        query = (
            supabase_client.table("agent_runs")
            .select("id,agent_name,session_id,output,completion_status,turns_count,created_at")
            .eq("user_id", user_id)
        )
        if agent_name:
            query = query.eq("agent_name", agent_name)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return res.data or []

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        logger.warning("agent_run_history_fetch_failed", error=str(exc), user_id=user_id)
        return []
