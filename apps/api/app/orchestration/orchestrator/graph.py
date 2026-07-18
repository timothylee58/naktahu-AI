"""SuperGraph definition — wires planner → router → executor → merger.

Execution flow:
  START → planner → (route_after_planner) →
    FAST PATH: executor → merger → END
    FULL PATH: router → executor → merger → END

The planner decides complexity. For simple/moderate queries with a known
fast_path_agent, the router is skipped (the planner already assigned the
agent). For complex multi-agent queries, the router runs full capability
scoring and dependency resolution before the executor fans out.

Compilation:
  compile_orchestrator() → compiled StateGraph (stateless, reusable)
  run_orchestrator(state) → one-shot invocation returning final state
"""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.orchestration.orchestrator.executor_node import executor_node
from app.orchestration.orchestrator.merger_node import merger_node
from app.orchestration.orchestrator.planner_node import planner_node
from app.orchestration.orchestrator.router_node import router_node
from app.orchestration.orchestrator.state import OrchestratorState


def _route_after_planner(state: OrchestratorState) -> str:
    """Decide whether to run the router or skip to executor.

    Fast path (skip router): planner set fast_path_agent and there's only
    one sub-task. The executor can run directly since the agent is known.

    Full path (run router): complex query with multiple sub-tasks needing
    capability-based agent assignment and dependency scheduling.
    """
    fast_path = state.get("fast_path_agent")
    sub_tasks = state.get("sub_tasks", [])

    if fast_path and len(sub_tasks) <= 1:
        # Fast path: assign agent directly in executor-ready format
        return "fast_path_prep"
    return "router"


async def _fast_path_prep_node(state: OrchestratorState) -> dict[str, Any]:
    """Prepare state for executor when planner selected fast-path.

    Copies sub_tasks to execution_plan with the fast_path_agent assigned,
    and creates a single parallel group. This avoids the router entirely
    for simple queries (saves ~100ms and one LLM call worth of latency).
    """
    sub_tasks = state.get("sub_tasks", [])
    fast_path = state.get("fast_path_agent", "knowledge-qa")

    if sub_tasks:
        sub_tasks[0]["target_agent"] = fast_path

    return {
        "execution_plan": sub_tasks,
        "parallel_groups": [[t["task_id"] for t in sub_tasks]] if sub_tasks else [],
    }


def build_orchestrator_graph() -> StateGraph:
    """Build the Orchestrator SuperGraph.

    Graph topology:
        START
          │
          ▼
       planner
          │
          ├─── (simple/moderate) ──→ fast_path_prep ──→ executor ──→ merger ──→ END
          │
          └─── (complex) ──→ router ──→ executor ──→ merger ──→ END
    """
    graph = StateGraph(OrchestratorState)

    # Register nodes
    graph.add_node("planner", planner_node)
    graph.add_node("router", router_node)
    graph.add_node("fast_path_prep", _fast_path_prep_node)
    graph.add_node("executor", executor_node)
    graph.add_node("merger", merger_node)

    # Edges
    graph.add_edge(START, "planner")

    # Conditional edge after planner: fast path or full routing
    graph.add_conditional_edges(
        "planner",
        _route_after_planner,
        {
            "fast_path_prep": "fast_path_prep",
            "router": "router",
        },
    )

    # Both paths converge at executor
    graph.add_edge("fast_path_prep", "executor")
    graph.add_edge("router", "executor")

    # Executor always goes to merger
    graph.add_edge("executor", "merger")

    # Merger is the terminal node
    graph.add_edge("merger", END)

    return graph


# ── Compilation and invocation ─────────────────────────────────────────────────

_compiled: Any = None


def compile_orchestrator():
    """Compile the orchestrator SuperGraph (cached singleton).

    Returns a compiled graph ready for .ainvoke() or .astream().
    Stateless — no checkpointer needed (orchestration sessions are
    request-scoped, not multi-turn).
    """
    global _compiled
    if _compiled is None:
        _compiled = build_orchestrator_graph().compile()
    return _compiled


async def run_orchestrator(
    query: str,
    *,
    language: str = "en",
    domain: str = "government",
    user_id: str = "",
    user_plan: str = "free",
    user_email: Optional[str] = None,
    session_id: str = "",
    correlation_id: str = "",
) -> OrchestratorState:
    """One-shot orchestrator invocation.

    Convenience wrapper that builds the initial state and runs the full
    pipeline. Returns the final state with merged results.

    For streaming, use the SSE endpoint which invokes the graph with
    .astream_events() instead.
    """
    import uuid

    if not session_id:
        session_id = str(uuid.uuid4())
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    initial_state: OrchestratorState = {
        "query": query,
        "language": language,
        "domain": domain,
        "user_id": user_id,
        "user_plan": user_plan,
        "user_email": user_email,
        "session_id": session_id,
        "correlation_id": correlation_id,
        "agent_results": [],
    }

    graph = compile_orchestrator()
    final_state = await graph.ainvoke(initial_state)
    return final_state
