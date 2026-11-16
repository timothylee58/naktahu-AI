"""Run-scoped dependencies passed to graph nodes via LangGraph `config`.

Live connection handles must NOT travel in graph state. Every state key is
serialised by the checkpointer on each write, and a Supabase `Client` holds an
`_thread.RLock`, so it is neither msgpack- nor pickle-serialisable — putting it
in state made `graph.ainvoke(...)` raise

    TypeError: Type is not msgpack serializable: Client

which surfaced as an unhandled HTTP 500 on `/start` for every agent that needed
a client (eligibility-agent, grant-draft-generator, compliance-drafter).

`config["configurable"]` entries are handed to nodes but are not checkpointed,
which is what a connection handle wants. `agent_runner._thread_config()` puts
the client there; nodes read it back through `supabase_from_config()`.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any


def thread_config(session_id: str, *, supabase: Any = None) -> dict[str, Any]:
    """Build a run's LangGraph config: `thread_id` for the checkpointer,
    `supabase` (if given) for nodes that need a client — see module
    docstring for why the client goes here and not into state.

    Single canonical implementation. Previously duplicated byte-for-byte
    into app/routers/eligibility.py's own module-local copy (confirmed
    cubic-dev-ai finding) — a fix to one would have silently left the
    other on the old behaviour and reintroduced the exact 500 this module
    exists to prevent.
    """
    configurable: dict[str, Any] = {"thread_id": session_id}
    if supabase is not None:
        configurable["supabase"] = supabase
    return {"configurable": configurable}


def supabase_from_config(config: Any) -> Any:
    """Return the run-scoped Supabase client, or None when absent.

    Returns None rather than raising when unset so nodes keep their existing
    degraded-mode behaviour (CLAUDE.md Trap #4) instead of crashing the graph.
    """
    if not config:
        return None
    configurable = config.get("configurable") if hasattr(config, "get") else None
    if not configurable:
        return None
    return configurable.get("supabase")


async def execute_query(builder: Any) -> Any:
    """Run a supabase-py query builder and return its response, for either client flavour.

    `app.state.supabase` is the SYNCHRONOUS client (`create_client`), whose `execute()` is a
    plain method: `await builder.execute()` raises `TypeError: object APIResponse can't be
    used in 'await' expression` AFTER the HTTP request has already succeeded, which nodes'
    broad `except Exception` then reported as "database unavailable". Sync executes run in a
    worker thread so they do not block the event loop; an async client's coroutine is
    awaited directly.
    """
    execute = builder.execute
    if inspect.iscoroutinefunction(execute):
        return await execute()
    result = await asyncio.to_thread(execute)
    return await result if inspect.isawaitable(result) else result
