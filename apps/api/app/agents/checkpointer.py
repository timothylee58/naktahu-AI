"""LangGraph checkpointer — PostgresSaver when DATABASE_URL is set, else MemorySaver."""
from __future__ import annotations

from typing import Any

import structlog

from core.config import settings

log = structlog.get_logger(__name__)

_checkpointer: Any = None


def get_checkpointer() -> Any:
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    from langgraph.checkpoint.memory import MemorySaver

    _checkpointer = MemorySaver()
    return _checkpointer


async def init_checkpointer() -> Any:
    """Call during app lifespan. Uses AsyncPostgresSaver when configured."""
    global _checkpointer
    db_url = settings.database_url.strip()
    if not db_url:
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        log.info("checkpointer_memory")
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver = AsyncPostgresSaver.from_conn_string(db_url)
        await saver.setup()
        _checkpointer = saver
        log.info("checkpointer_postgres")
        return _checkpointer
    except Exception as exc:
        log.warning("checkpointer_postgres_failed", error=str(exc))
        from langgraph.checkpoint.memory import MemorySaver

        _checkpointer = MemorySaver()
        return _checkpointer


def reset_checkpointer_for_tests() -> None:
    global _checkpointer
    _checkpointer = None
