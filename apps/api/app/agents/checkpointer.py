"""LangGraph checkpointer — PostgresSaver when DATABASE_URL is set, else MemorySaver."""
from __future__ import annotations

from typing import Any

import structlog

from core.config import settings

log = structlog.get_logger(__name__)

_checkpointer: Any = None
# Tracks which backend is actually live so it's observable (GET /health)
# rather than only a one-line log at boot. A Postgres-checkpoint failure at
# startup previously fell back to MemorySaver silently enough that the only
# symptom was "the agent forgot the conversation" after the next restart —
# every in-flight multi-turn session (eligibility intake, immigration
# navigator, study-agent quiz) is lost with no visible signal otherwise.
# Found during a full-codebase complexity trace.
_checkpointer_backend: str = "unknown"
# The Postgres connection pool behind the saver, closed by close_checkpointer().
_pool: Any = None


def get_checkpointer() -> Any:
    global _checkpointer, _checkpointer_backend
    if _checkpointer is not None:
        return _checkpointer
    from langgraph.checkpoint.memory import MemorySaver

    _checkpointer = MemorySaver()
    _checkpointer_backend = "memory"
    return _checkpointer


def get_checkpointer_backend() -> str:
    """'postgres' | 'memory' | 'unknown' (before init_checkpointer has run)."""
    return _checkpointer_backend


async def init_checkpointer() -> Any:
    """Call during app lifespan. Uses AsyncPostgresSaver when configured."""
    global _checkpointer, _checkpointer_backend, _pool
    db_url = settings.database_url.strip()
    if not db_url:
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        _checkpointer_backend = "memory"
        log.info("checkpointer_memory")
        return _checkpointer

    pool: Any = None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        # AsyncPostgresSaver.from_conn_string() is an async CONTEXT MANAGER that
        # closes its connection on exit, not a saver: calling .setup() on its
        # return value raised AttributeError, so Postgres could never be used
        # even with libpq present. Own the connections instead, as a pool that
        # lives for the app's lifetime and replaces connections the server drops
        # (Supabase closes idle ones). Settings are the ones the saver requires.
        pool = AsyncConnectionPool(
            conninfo=db_url,
            max_size=5,
            open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        await pool.open(wait=True, timeout=10)
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        _checkpointer = saver
        _pool = pool
        _checkpointer_backend = "postgres"
        log.info("checkpointer_postgres")
        return _checkpointer
    except Exception as exc:
        # error, not warning — this is a silent, persistent degradation
        # (every multi-turn agent session loses state on the next restart),
        # not a one-off recoverable event; it deserves to page, not scroll by.
        log.error("checkpointer_postgres_failed_falling_back_to_memory", error=str(exc))
        if pool is not None:
            try:
                await pool.close()
            except Exception:  # best effort: we are already on the failure path
                pass
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        _checkpointer_backend = "memory"
        return _checkpointer


async def close_checkpointer() -> None:
    """Call at app shutdown: close the Postgres pool, if one was opened."""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception as exc:
            log.warning("checkpointer_pool_close_failed", error=str(exc))
        _pool = None


def reset_checkpointer_for_tests() -> None:
    global _checkpointer, _checkpointer_backend
    _checkpointer = None
    _checkpointer_backend = "unknown"
