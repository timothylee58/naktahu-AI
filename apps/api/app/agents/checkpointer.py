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
    global _checkpointer, _checkpointer_backend
    db_url = settings.database_url.strip()
    if not db_url:
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        _checkpointer_backend = "memory"
        log.info("checkpointer_memory")
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver = AsyncPostgresSaver.from_conn_string(db_url)
        await saver.setup()
        _checkpointer = saver
        _checkpointer_backend = "postgres"
        log.info("checkpointer_postgres")
        return _checkpointer
    except Exception as exc:
        # error, not warning — this is a silent, persistent degradation
        # (every multi-turn agent session loses state on the next restart),
        # not a one-off recoverable event; it deserves to page, not scroll by.
        log.error("checkpointer_postgres_failed_falling_back_to_memory", error=str(exc))
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        _checkpointer_backend = "memory"
        return _checkpointer


def reset_checkpointer_for_tests() -> None:
    global _checkpointer, _checkpointer_backend
    _checkpointer = None
    _checkpointer_backend = "unknown"
