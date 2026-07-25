"""executor_node — parallel agent execution via LangGraph Send().

Executes sub-tasks by invoking the appropriate agent adapters. Uses
LangGraph's Send() API to fan out independent tasks in parallel, while
sequential dependencies run in waves (group by group).

Architecture:
- dispatch_node: reads parallel_groups and emits Send() for the current wave
- agent_worker_node: receives a single task, invokes the adapter, returns result
- The SuperGraph wires these with conditional edges so each wave completes
  before the next dispatches.

For the initial implementation, we use a simpler approach that works with
LangGraph's StateGraph:
- A single executor_node iterates through parallel_groups
- Within each group, tasks are gathered via asyncio.gather (true parallelism)
- Results are accumulated into agent_results (operator.add reducer)

This gives us real parallel execution without requiring the more complex
Send()-based fan-out pattern, which we can migrate to in a future iteration
once the orchestrator is proven.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from app.orchestration.context import OrchestratorContext
from app.orchestration.metrics import record_agent_call
from app.orchestration.orchestrator.state import (
    AgentExecutionResult,
    OrchestratorState,
    SubTaskState,
)
from app.orchestration.registry import get_adapter
from app.orchestration.types import AgentResult, AgentStatusEnum
from services.auth import UserContext

log = structlog.get_logger(__name__)

_MAX_CONCURRENT_PER_GROUP = 4  # Cap parallelism to avoid overwhelming LLM APIs


def _build_agent_context(
    task: SubTaskState,
    state: OrchestratorState,
    shared_findings: tuple[dict[str, Any], ...] = (),
) -> OrchestratorContext:
    """Build an OrchestratorContext for a specific sub-task invocation."""
    user: UserContext | None = None
    user_id = state.get("user_id", "")
    user_plan = state.get("user_plan", "free")
    user_email = state.get("user_email")

    if user_id:
        user = UserContext(
            user_id=user_id,
            is_anonymous=False,
            plan=user_plan,
            email=user_email,
        )

    return OrchestratorContext(
        query=task.get("description", state.get("query", "")),
        language=state.get("language", "en"),
        domain=task.get("domain", "government"),
        user=user,
        session_id=state.get("session_id", ""),
        parent_session_id=state.get("session_id"),
        correlation_id=state.get("correlation_id", ""),
        shared_findings=shared_findings,
        timeout_seconds=30.0,
        stream=False,  # Executor runs non-streaming; SSE streams at outer layer
        extra={},
    )


def _result_to_execution_result(
    task: SubTaskState,
    result: AgentResult,
) -> AgentExecutionResult:
    """Convert an AgentResult to the executor's output format."""
    return AgentExecutionResult(
        task_id=task.get("task_id", ""),
        agent_name=result.agent_name,
        status=result.status.value,
        output=result.output,
        structured_output=result.structured_output,
        citations=[c.model_dump() for c in result.citations],
        confidence=result.confidence,
        suggestions=result.suggestions,
        error=result.error,
        latency_ms=result.latency_ms,
        output_flagged=result.output_flagged,
    )


async def _execute_single_task(
    task: SubTaskState,
    state: OrchestratorState,
    shared_findings: tuple[dict[str, Any], ...] = (),
) -> AgentExecutionResult:
    """Execute a single sub-task by invoking its assigned agent adapter.

    Returns a result even on failure (status=failed with error message),
    so the merger always has something to work with.
    """
    agent_name = task.get("target_agent", "knowledge-qa")
    task_id = task.get("task_id", "unknown")

    adapter = get_adapter(agent_name)
    if not adapter:
        log.warning("executor_no_adapter", agent=agent_name, task_id=task_id)
        record_agent_call(agent_name, success=False, latency_ms=0.0)
        return AgentExecutionResult(
            task_id=task_id,
            agent_name=agent_name,
            status=AgentStatusEnum.failed.value,
            output="",
            structured_output={},
            citations=[],
            confidence=0.0,
            suggestions=[],
            error=f"No adapter registered for agent '{agent_name}'",
            latency_ms=0.0,
            output_flagged=False,
        )

    context = _build_agent_context(task, state, shared_findings)

    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(
            adapter.start(context),
            timeout=context.timeout_seconds,
        )
    except asyncio.TimeoutError:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        log.warning("executor_task_timeout", agent=agent_name, task_id=task_id, ms=elapsed)
        record_agent_call(agent_name, success=False, latency_ms=elapsed, timeout=True)
        return AgentExecutionResult(
            task_id=task_id,
            agent_name=agent_name,
            status=AgentStatusEnum.timed_out.value,
            output="",
            structured_output={},
            citations=[],
            confidence=0.0,
            suggestions=[],
            error=f"Agent '{agent_name}' timed out after {context.timeout_seconds}s",
            latency_ms=elapsed,
            output_flagged=False,
        )
    except Exception as exc:
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        log.error("executor_task_failed", agent=agent_name, task_id=task_id, error=str(exc))
        record_agent_call(agent_name, success=False, latency_ms=elapsed)
        return AgentExecutionResult(
            task_id=task_id,
            agent_name=agent_name,
            status=AgentStatusEnum.failed.value,
            output="",
            structured_output={},
            citations=[],
            confidence=0.0,
            suggestions=[],
            error=str(exc),
            latency_ms=elapsed,
            output_flagged=False,
        )

    log.info(
        "executor_task_done",
        agent=agent_name,
        task_id=task_id,
        status=result.status.value,
        latency_ms=result.latency_ms,
    )
    record_agent_call(
        agent_name,
        success=(result.status == AgentStatusEnum.completed),
        latency_ms=result.latency_ms,
        confidence=result.confidence,
        timeout=(result.status == AgentStatusEnum.timed_out),
        flagged=result.output_flagged,
        cache_hit=result.cache_hit,
        tokens_used=result.tokens_used,
    )
    return _result_to_execution_result(task, result)


async def executor_node(state: OrchestratorState) -> dict[str, Any]:
    """Execute all sub-tasks respecting parallel groups and dependencies.

    Iterates through parallel_groups in order. Within each group, tasks
    are dispatched concurrently via asyncio.gather. Results from earlier
    groups are passed as shared_findings to later groups, enabling
    dependent tasks to build on sibling outputs.
    """
    execution_plan: list[SubTaskState] = state.get("execution_plan", [])
    parallel_groups: list[list[str]] = state.get("parallel_groups", [])

    if not execution_plan or not parallel_groups:
        log.warning("executor_empty_plan")
        return {"agent_results": []}

    # Build task lookup
    task_map: dict[str, SubTaskState] = {
        t["task_id"]: t for t in execution_plan
    }

    all_results: list[AgentExecutionResult] = []
    shared_findings: tuple[dict[str, Any], ...] = ()

    for group_idx, group_task_ids in enumerate(parallel_groups):
        tasks_in_group = [
            task_map[tid] for tid in group_task_ids if tid in task_map
        ]

        if not tasks_in_group:
            continue

        log.info(
            "executor_group_start",
            group=group_idx,
            tasks=len(tasks_in_group),
            agents=[t.get("target_agent", "?") for t in tasks_in_group],
        )

        # Execute tasks in this group concurrently (capped)
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PER_GROUP)

        async def _run_with_semaphore(task: SubTaskState) -> AgentExecutionResult:
            async with semaphore:
                return await _execute_single_task(task, state, shared_findings)

        group_results = await asyncio.gather(
            *[_run_with_semaphore(t) for t in tasks_in_group],
            return_exceptions=False,
        )

        all_results.extend(group_results)

        # Build shared findings for the next group from completed results
        new_findings: list[dict[str, Any]] = []
        for r in group_results:
            if r.get("status") == "completed" and r.get("output"):
                new_findings.append({
                    "agent": r.get("agent_name", ""),
                    "task_id": r.get("task_id", ""),
                    "output": r.get("output", ""),
                    "citations": r.get("citations", []),
                })
        shared_findings = shared_findings + tuple(new_findings)

    log.info(
        "executor_done",
        total_tasks=len(all_results),
        completed=sum(1 for r in all_results if r.get("status") == "completed"),
        failed=sum(1 for r in all_results if r.get("status") in ("failed", "timed_out")),
    )

    return {"agent_results": all_results}
