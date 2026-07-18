"""router_node — maps sub-tasks to agents via capability scoring.

Takes the planner's sub-tasks and uses the enhanced registry's
get_best_agents_for_task() to assign the optimal agent to each one.
Also builds the parallel_groups execution schedule — grouping independent
tasks together for fan-out, while respecting dependency chains.

If fast_path_agent is set by the planner, the router short-circuits:
it assigns that agent directly without scoring, since the planner already
determined single-agent routing.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.orchestration.orchestrator.state import OrchestratorState, SubTaskState
from app.orchestration.registry import get_best_agents_for_task, plan_satisfies
from app.orchestration.types import AgentCapability

log = structlog.get_logger(__name__)


def _resolve_capabilities(raw: list[str]) -> list[AgentCapability]:
    """Convert string capability names to AgentCapability enums safely."""
    resolved: list[AgentCapability] = []
    for cap_str in raw:
        try:
            resolved.append(AgentCapability(cap_str))
        except ValueError:
            pass
    return resolved


def _assign_agent_to_task(
    task: SubTaskState,
    user_plan: str,
) -> str:
    """Score candidate agents and return the best match name.

    Falls back to 'knowledge-qa' when no agent scores above threshold or
    when the best agent isn't accessible on the user's plan.
    """
    domain = task.get("domain", "government")
    capabilities_needed = _resolve_capabilities(task.get("capabilities_needed", []))

    ranked = get_best_agents_for_task(
        domain=domain,
        capabilities_needed=capabilities_needed,
        user_plan=user_plan,
        limit=3,
    )

    if not ranked:
        return "knowledge-qa"

    # Pick the highest-scoring agent that the user can access
    for defn, score in ranked:
        if plan_satisfies(user_plan, defn.plan_required):
            return defn.name

    # If no accessible agent found, fall back to knowledge-qa (always free)
    return "knowledge-qa"


def _build_parallel_groups(tasks: list[SubTaskState]) -> list[list[str]]:
    """Build execution groups respecting dependency chains.

    Tasks with no unresolved dependencies go in the earliest possible group.
    This produces a topological ordering grouped by execution wave:
      - Group 0: all tasks with no depends_on (run in parallel)
      - Group 1: tasks whose dependencies are all in group 0
      - Group N: tasks whose dependencies are all in groups < N

    Returns a list of groups, each containing task_ids that can execute
    concurrently within the group.
    """
    task_map = {t["task_id"]: t for t in tasks}
    assigned: dict[str, int] = {}  # task_id -> group index
    groups: list[list[str]] = []

    max_iterations = len(tasks) + 1  # prevent infinite loops on bad deps
    iteration = 0

    while len(assigned) < len(tasks) and iteration < max_iterations:
        iteration += 1
        current_group: list[str] = []

        for task in tasks:
            tid = task["task_id"]
            if tid in assigned:
                continue

            deps = task.get("depends_on", [])
            # A task is ready if all its dependencies have been assigned
            all_deps_resolved = all(d in assigned for d in deps)
            if all_deps_resolved:
                current_group.append(tid)

        if not current_group:
            # Circular dependency or invalid deps — force remaining into one group
            remaining = [t["task_id"] for t in tasks if t["task_id"] not in assigned]
            groups.append(remaining)
            break

        for tid in current_group:
            assigned[tid] = len(groups)
        groups.append(current_group)

    return groups


async def router_node(state: OrchestratorState) -> dict[str, Any]:
    """Assign agents to sub-tasks and build execution schedule.

    If the planner set fast_path_agent, this node simply assigns that agent
    to the single sub-task without scoring. For complex queries it runs
    full capability-based scoring and dependency resolution.
    """
    sub_tasks: list[SubTaskState] = state.get("sub_tasks", [])
    fast_path = state.get("fast_path_agent")
    user_plan = state.get("user_plan", "free")

    if not sub_tasks:
        log.warning("router_no_sub_tasks")
        return {
            "execution_plan": [],
            "parallel_groups": [],
        }

    # Fast-path: planner already determined the agent
    if fast_path and len(sub_tasks) == 1:
        sub_tasks[0]["target_agent"] = fast_path
        log.info("router_fast_path", agent=fast_path)
        return {
            "execution_plan": sub_tasks,
            "parallel_groups": [[sub_tasks[0]["task_id"]]],
        }

    # Full routing: score each sub-task against the registry
    for task in sub_tasks:
        agent_name = _assign_agent_to_task(task, user_plan)
        task["target_agent"] = agent_name

    # Build parallel execution groups from dependency graph
    parallel_groups = _build_parallel_groups(sub_tasks)

    agents_assigned = [t.get("target_agent", "?") for t in sub_tasks]
    log.info(
        "router_done",
        tasks=len(sub_tasks),
        groups=len(parallel_groups),
        agents=agents_assigned,
    )

    return {
        "execution_plan": sub_tasks,
        "parallel_groups": parallel_groups,
    }
