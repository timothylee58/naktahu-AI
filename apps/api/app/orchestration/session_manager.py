"""Session TTL manager — cleanup for abandoned agent sessions.

Multi-turn agents (compliance-drafter, immigration-navigator, study-agent)
create checkpointed sessions that persist indefinitely. Abandoned sessions
(user started intake but never finished) accumulate in the database.

This module provides:
1. TTL-based cleanup: delete sessions older than max_age
2. Startup cleanup: run once on app boot to clear stale sessions
3. Metrics: track active/abandoned/cleaned session counts

Sessions are stored in the agent_sessions table with an updated_at column.
The cleanup query deletes rows where updated_at < (now - max_age).

Configuration:
- SESSION_MAX_AGE_HOURS: env var, default 72 (3 days)
- SESSION_CLEANUP_BATCH_SIZE: env var, default 100
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog

log = structlog.get_logger(__name__)

SESSION_MAX_AGE_HOURS = int(os.environ.get("SESSION_MAX_AGE_HOURS", "72"))
SESSION_CLEANUP_BATCH_SIZE = int(os.environ.get("SESSION_CLEANUP_BATCH_SIZE", "100"))


from dataclasses import dataclass


@dataclass
class CleanupResult:
    """Result of a session cleanup run."""

    deleted_count: int = 0
    error: Optional[str] = None
    duration_ms: float = 0.0
    cutoff_time: Optional[str] = None


async def cleanup_abandoned_sessions(
    supabase_client: Any,
    *,
    max_age_hours: int = SESSION_MAX_AGE_HOURS,
    batch_size: int = SESSION_CLEANUP_BATCH_SIZE,
) -> CleanupResult:
    """Delete agent sessions older than max_age_hours.

    Runs against the agent_sessions table. Only deletes sessions that have
    NOT been updated within the TTL window — active sessions are safe.

    Returns a CleanupResult with the count of deleted rows.
    """
    import asyncio
    import time

    if not supabase_client:
        return CleanupResult(error="Supabase client not available")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    cutoff_iso = cutoff.isoformat()

    t0 = time.monotonic()
    try:
        def _delete() -> int:
            res = (
                supabase_client.table("agent_sessions")
                .delete()
                .lt("updated_at", cutoff_iso)
                .limit(batch_size)
                .execute()
            )
            return len(res.data) if res.data else 0

        deleted = await asyncio.to_thread(_delete)
        elapsed = round((time.monotonic() - t0) * 1000, 1)

        if deleted > 0:
            log.info(
                "session_cleanup_done",
                deleted=deleted,
                cutoff=cutoff_iso,
                max_age_hours=max_age_hours,
                duration_ms=elapsed,
            )
        else:
            log.debug("session_cleanup_none", cutoff=cutoff_iso)

        return CleanupResult(
            deleted_count=deleted,
            duration_ms=elapsed,
            cutoff_time=cutoff_iso,
        )
    except Exception as exc:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        log.warning("session_cleanup_failed", error=str(exc), duration_ms=elapsed)
        return CleanupResult(error=str(exc), duration_ms=elapsed, cutoff_time=cutoff_iso)


async def get_session_stats(supabase_client: Any) -> dict[str, Any]:
    """Get session count statistics for the metrics endpoint.

    Returns counts of active vs stale sessions per agent.
    """
    import asyncio

    if not supabase_client:
        return {"error": "Supabase client not available"}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_MAX_AGE_HOURS)
    cutoff_iso = cutoff.isoformat()

    try:
        def _query() -> dict[str, Any]:
            # Total sessions per agent
            total_res = (
                supabase_client.table("agent_sessions")
                .select("agent_name")
                .execute()
            )
            total_rows = total_res.data or []

            # Stale sessions (older than TTL)
            stale_res = (
                supabase_client.table("agent_sessions")
                .select("agent_name")
                .lt("updated_at", cutoff_iso)
                .execute()
            )
            stale_rows = stale_res.data or []

            # Count by agent
            from collections import Counter
            total_counts = Counter(r.get("agent_name", "unknown") for r in total_rows)
            stale_counts = Counter(r.get("agent_name", "unknown") for r in stale_rows)

            return {
                "total_sessions": len(total_rows),
                "stale_sessions": len(stale_rows),
                "active_sessions": len(total_rows) - len(stale_rows),
                "max_age_hours": SESSION_MAX_AGE_HOURS,
                "by_agent": {
                    agent: {
                        "total": count,
                        "stale": stale_counts.get(agent, 0),
                        "active": count - stale_counts.get(agent, 0),
                    }
                    for agent, count in total_counts.items()
                },
            }

        return await asyncio.to_thread(_query)
    except Exception as exc:
        log.warning("session_stats_failed", error=str(exc))
        return {"error": str(exc)}
