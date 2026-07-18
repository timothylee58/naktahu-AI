"""Multi-agent orchestration SSE endpoint.

POST /api/v1/orchestrate — streams real-time events as the orchestrator
decomposes a query, dispatches agents, and merges results.

SSE Event Types:
  - planning       : planner has decomposed the query
  - agent_start    : an agent is about to execute
  - agent_done     : an agent completed (with output snippet)
  - agent_failed   : an agent failed or timed out
  - synthesis      : merger is producing final output
  - citation       : a merged citation
  - metadata       : overall stats (confidence, latency, agents_used)
  - done           : stream complete
  - error          : unrecoverable error

This extends the existing SSE contract (token, citation, metadata, done, error)
with orchestration-specific events (planning, agent_start, agent_done, synthesis).
The frontend can progressively render which agents are working in real time.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Annotated, Any, AsyncGenerator, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.middleware.sanitise import sanitise_query
from app.orchestration.context import OrchestratorContext
from app.orchestration.context_bus import ContextBus
from app.orchestration.orchestrator.executor_node import _build_agent_context, _execute_single_task
from app.orchestration.orchestrator.merger_node import (
    _aggregate_suggestions,
    _compute_overall_confidence,
    _deduplicate_citations,
    _synthesize_multi_agent,
)
from app.orchestration.orchestrator.planner_node import planner_node
from app.orchestration.orchestrator.router_node import router_node
from app.orchestration.orchestrator.state import (
    AgentExecutionResult,
    OrchestratorState,
    SubTaskState,
)
from app.orchestration.registry import get_adapter, plan_satisfies
from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user, get_optional_user

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["orchestrate"])


class OrchestrateRequest(BaseModel):
    """Request body for the orchestration endpoint."""

    query: str = Field(..., min_length=2, max_length=1000)
    language: Optional[str] = Field(None, pattern=r"^(bm|en|zh)$")
    domain: Optional[str] = None


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a single SSE event line."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


async def _stream_orchestration(
    query: str,
    language: str,
    domain: str,
    user: Optional[UserContext],
    context_bus: Optional[ContextBus],
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE events as orchestration progresses.

    Runs the orchestrator nodes manually (not via compiled graph) to emit
    fine-grained SSE events between each stage. This gives the frontend
    real-time visibility into which agents are working.
    """
    session_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    t0 = time.monotonic()

    user_id = user.user_id if user else ""
    user_plan = user.plan if user else "free"
    user_email = user.email if user else None

    # Build initial state
    state: OrchestratorState = {
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

    # ── Stage 1: Planning ──────────────────────────────────────────────────
    try:
        planner_result = await planner_node(state)
        state.update(planner_result)
    except Exception as exc:
        log.error("orchestrate_planner_failed", error=str(exc))
        yield _sse_event("error", {"message": "Planning failed", "detail": str(exc)})
        return

    complexity = state.get("complexity", "simple")
    sub_tasks: list[SubTaskState] = state.get("sub_tasks", [])
    fast_path = state.get("fast_path_agent")

    yield _sse_event("planning", {
        "session_id": session_id,
        "complexity": complexity,
        "reasoning": state.get("reasoning", ""),
        "sub_tasks": [
            {"task_id": t["task_id"], "description": t.get("description", ""), "domain": t.get("domain", "")}
            for t in sub_tasks
        ],
        "fast_path_agent": fast_path,
    })

    # ── Stage 2: Routing ───────────────────────────────────────────────────
    if fast_path and len(sub_tasks) <= 1:
        # Fast path: assign directly
        if sub_tasks:
            sub_tasks[0]["target_agent"] = fast_path
        state["execution_plan"] = sub_tasks
        state["parallel_groups"] = [[t["task_id"] for t in sub_tasks]] if sub_tasks else []
    else:
        try:
            router_result = await router_node(state)
            state.update(router_result)
        except Exception as exc:
            log.error("orchestrate_router_failed", error=str(exc))
            yield _sse_event("error", {"message": "Routing failed", "detail": str(exc)})
            return

    execution_plan: list[SubTaskState] = state.get("execution_plan", [])
    parallel_groups: list[list[str]] = state.get("parallel_groups", [])

    # ── Stage 3: Execution (with per-agent SSE events) ─────────────────────
    task_map = {t["task_id"]: t for t in execution_plan}
    all_results: list[AgentExecutionResult] = []
    shared_findings: tuple[dict[str, Any], ...] = ()

    for group_idx, group_task_ids in enumerate(parallel_groups):
        tasks_in_group = [task_map[tid] for tid in group_task_ids if tid in task_map]
        if not tasks_in_group:
            continue

        # Emit agent_start for all tasks in this group
        for task in tasks_in_group:
            yield _sse_event("agent_start", {
                "task_id": task["task_id"],
                "agent": task.get("target_agent", "unknown"),
                "description": task.get("description", ""),
                "group": group_idx,
            })

        # Execute group concurrently
        semaphore = asyncio.Semaphore(4)

        async def _run(task: SubTaskState) -> AgentExecutionResult:
            async with semaphore:
                return await _execute_single_task(task, state, shared_findings)

        group_results = await asyncio.gather(
            *[_run(t) for t in tasks_in_group],
            return_exceptions=False,
        )

        # Emit agent_done / agent_failed for each result
        for result in group_results:
            task_id = result.get("task_id", "")
            agent_name = result.get("agent_name", "")
            status = result.get("status", "failed")

            if status == "completed":
                # Truncate output for SSE (full output comes in synthesis)
                snippet = (result.get("output", "") or "")[:200]
                yield _sse_event("agent_done", {
                    "task_id": task_id,
                    "agent": agent_name,
                    "status": status,
                    "snippet": snippet,
                    "confidence": result.get("confidence", 0.0),
                    "latency_ms": result.get("latency_ms", 0.0),
                })
            else:
                yield _sse_event("agent_failed", {
                    "task_id": task_id,
                    "agent": agent_name,
                    "status": status,
                    "error": result.get("error", "Unknown error"),
                })

        all_results.extend(group_results)

        # Build shared findings for next group
        new_findings = [
            {"agent": r.get("agent_name", ""), "task_id": r.get("task_id", ""), "output": r.get("output", "")}
            for r in group_results
            if r.get("status") == "completed" and r.get("output")
        ]
        shared_findings = shared_findings + tuple(new_findings)

    state["agent_results"] = all_results

    # Publish to context bus if available
    if context_bus and context_bus.available:
        for r in all_results:
            if r.get("status") == "completed":
                await context_bus.publish_agent_output(
                    correlation_id,
                    r.get("agent_name", ""),
                    r.get("structured_output", {}),
                )

    # ── Stage 4: Synthesis / Merge ─────────────────────────────────────────
    yield _sse_event("synthesis", {"status": "started", "agents_completed": len(all_results)})

    completed_results = [r for r in all_results if r.get("status") == "completed" and r.get("output")]

    if not completed_results:
        final_output = {
            "bm": "Maaf, sistem tidak dapat memproses permintaan anda sekarang. Sila cuba lagi.",
            "zh": "抱歉，系统目前无法处理您的请求。请稍后再试。",
        }.get(language, "Sorry, the system was unable to process your request. Please try again.")
    elif len(completed_results) == 1:
        final_output = completed_results[0].get("output", "")
    else:
        final_output = await _synthesize_multi_agent(query, language, completed_results)

    # Deduplicate citations
    all_citations: list[dict[str, Any]] = []
    for r in all_results:
        all_citations.extend(r.get("citations", []))
    merged_citations = _deduplicate_citations(all_citations)

    # Emit citations
    for citation in merged_citations:
        yield _sse_event("citation", citation)

    # Emit the final synthesized output
    yield _sse_event("synthesis", {"status": "completed", "output": final_output})

    # ── Stage 5: Metadata & Done ───────────────────────────────────────────
    total_latency = round((time.monotonic() - t0) * 1000, 1)
    agents_used = list({r.get("agent_name", "") for r in all_results if r.get("agent_name")})
    overall_confidence = _compute_overall_confidence(all_results)
    suggestions = _aggregate_suggestions(all_results)
    output_flagged = any(r.get("output_flagged", False) for r in all_results)

    yield _sse_event("metadata", {
        "session_id": session_id,
        "complexity": complexity,
        "agents_used": agents_used,
        "overall_confidence": overall_confidence,
        "total_latency_ms": total_latency,
        "suggestions": suggestions,
        "output_flagged": output_flagged,
    })

    yield _sse_event("done", {"session_id": session_id})

    # Cleanup context bus
    if context_bus and context_bus.available:
        await context_bus.clear(correlation_id)


@router.post("/orchestrate")
async def orchestrate_query(
    body: OrchestrateRequest,
    request: Request,
    response: Response,
    user: Annotated[Optional[UserContext], Depends(get_optional_user)],
):
    """Multi-agent orchestration endpoint with SSE streaming.

    Decomposes the query, dispatches to optimal agents in parallel, and
    streams real-time progress events showing which agents are working.

    Returns text/event-stream with events:
      planning, agent_start, agent_done, agent_failed, synthesis, citation, metadata, done, error
    """
    # Sanitise input (same as /query endpoint)
    try:
        query = sanitise_query(body.query)
    except HTTPException:
        raise

    language = body.language or "en"
    domain = body.domain or "government"

    # Get context bus from app state
    context_bus: Optional[ContextBus] = getattr(request.app.state, "context_bus", None)

    return StreamingResponse(
        _stream_orchestration(query, language, domain, user, context_bus),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/orchestrate/sync")
async def orchestrate_query_sync(
    body: OrchestrateRequest,
    request: Request,
    response: Response,
    user: Annotated[Optional[UserContext], Depends(get_optional_user)],
) -> dict[str, Any]:
    """Non-streaming orchestration endpoint (for programmatic use).

    Same logic as /orchestrate but returns a single JSON response instead
    of SSE stream. Useful for API integrations that don't support streaming.
    """
    from app.orchestration.orchestrator.graph import run_orchestrator

    try:
        query = sanitise_query(body.query)
    except HTTPException:
        raise

    language = body.language or "en"
    domain = body.domain or "government"
    user_id = user.user_id if user else ""
    user_plan = user.plan if user else "free"
    user_email = user.email if user else None

    result = await run_orchestrator(
        query=query,
        language=language,
        domain=domain,
        user_id=user_id,
        user_plan=user_plan,
        user_email=user_email,
    )

    return {
        "session_id": result.get("session_id", ""),
        "complexity": result.get("complexity", "simple"),
        "final_output": result.get("final_output", ""),
        "citations": result.get("merged_citations", []),
        "overall_confidence": result.get("overall_confidence", 0.0),
        "suggestions": result.get("suggestions", []),
        "agents_used": result.get("agents_used", []),
        "total_latency_ms": result.get("total_latency_ms", 0.0),
        "output_flagged": result.get("output_flagged", False),
    }
