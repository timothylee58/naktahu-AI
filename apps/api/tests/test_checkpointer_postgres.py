"""The Postgres checkpointer: a session must survive a different process.

Production runs two uvicorn workers. With the in-memory fallback, a confirm that
lands on the other worker cannot find the session. These tests cover the
Postgres path (which silently never worked: AsyncPostgresSaver.from_conn_string
is a context manager, not a saver) and the fallback when Postgres is unreachable.
"""
from __future__ import annotations

import importlib
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import checkpointer as cp
from core.config import settings

_PG_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(autouse=True)
def _reset() -> Any:
    cp.reset_checkpointer_for_tests()
    yield
    cp.reset_checkpointer_for_tests()


@pytest.mark.asyncio
async def test_unreachable_postgres_falls_back_to_memory_and_closes_the_pool() -> None:
    # Import first: the saver module binds AsyncConnectionPool at import time, so
    # importing it for the first time under the patch below would keep the mock.
    importlib.import_module("langgraph.checkpoint.postgres.aio")

    pool = MagicMock()
    pool.open = AsyncMock(side_effect=RuntimeError("connection refused"))
    pool.close = AsyncMock()
    with (
        patch.object(settings, "database_url", "postgresql://nobody@127.0.0.1:1/none"),
        patch("psycopg_pool.AsyncConnectionPool", return_value=pool),
    ):
        saver = await cp.init_checkpointer()

    assert cp.get_checkpointer_backend() == "memory"
    assert type(saver).__name__ in {"InMemorySaver", "MemorySaver"}
    pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_database_url_uses_memory() -> None:
    with patch.object(settings, "database_url", ""):
        await cp.init_checkpointer()
    assert cp.get_checkpointer_backend() == "memory"


@pytest.mark.asyncio
async def test_close_without_a_pool_is_a_no_op() -> None:
    await cp.close_checkpointer()


@pytest.mark.skipif(not _PG_URL, reason="set TEST_DATABASE_URL to a throwaway Postgres to run")
@pytest.mark.asyncio
async def test_a_session_survives_a_different_worker() -> None:
    from app.agents.compliance_drafter import nodes
    from app.services import agent_runner

    empty = {"current": [], "announced": [], "dropped": {"superseded": 0, "expired": 0, "low_relevance": 0}}

    async def pdf(_html: str, **_k: Any) -> tuple[str, str, str]:
        return "p.pdf", "https://signed.example/r.pdf", "2030-01-01T00:00:00+00:00"

    with (
        patch.object(settings, "database_url", _PG_URL),
        patch.object(nodes, "query_rag_freshness", AsyncMock(return_value=empty)),
        patch("app.agents.tools.generate_pdf", pdf),
        patch("app.agents.tools.send_email", AsyncMock(return_value=True)),
    ):
        worker_a = await cp.init_checkpointer()
        assert cp.get_checkpointer_backend() == "postgres"
        started = await agent_runner.start_compliance_drafter(
            user_id="u1", user_email=None, payload={}, supabase_client=None, checkpointer=worker_a
        )

        # A second worker: no shared memory, same database.
        await cp.close_checkpointer()
        cp.reset_checkpointer_for_tests()
        worker_b = await cp.init_checkpointer()
        out = await agent_runner.confirm_compliance_drafter(
            session_id=started["session_id"], user_id="u1", user_email=None, supabase_client=None, checkpointer=worker_b
        )
        await cp.close_checkpointer()

    assert out["status"] == "completed"
    assert out["signed_url"] == "https://signed.example/r.pdf"


@pytest.mark.skipif(not _PG_URL, reason="set TEST_DATABASE_URL to a throwaway Postgres to run")
@pytest.mark.asyncio
async def test_workers_booting_together_on_a_fresh_database_all_get_postgres() -> None:
    """saver.setup() alone races: concurrent first boots hit a unique violation."""
    import asyncio

    import psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    conn = await psycopg.AsyncConnection.connect(_PG_URL, autocommit=True)
    await conn.execute(
        "DROP TABLE IF EXISTS checkpoint_migrations, checkpoints, checkpoint_blobs, checkpoint_writes CASCADE"
    )
    await conn.close()

    async def worker() -> str:
        pool = AsyncConnectionPool(
            conninfo=_PG_URL,
            max_size=5,
            open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        await pool.open(wait=True, timeout=10)
        try:
            await cp.setup_schema(pool, AsyncPostgresSaver(pool))
            return "ok"
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        finally:
            await pool.close()

    results = await asyncio.gather(*[worker() for _ in range(4)])
    assert results == ["ok"] * 4
