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

from typing import Any


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
