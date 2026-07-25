"""Observability endpoints — metrics, spans, session stats, safety status.

Provides admin/monitoring visibility into the agent orchestration layer.
All endpoints require authentication (at minimum). The /metrics and /spans
endpoints are designed for dashboards and alerting systems.

Endpoints:
  GET /api/v1/observability/metrics         — per-agent performance metrics
  GET /api/v1/observability/metrics/summary — high-level system summary
  GET /api/v1/observability/metrics/{agent} — metrics for a specific agent
  GET /api/v1/observability/spans           — recent telemetry spans
  GET /api/v1/observability/sessions        — session count stats
  POST /api/v1/observability/sessions/cleanup — trigger manual session cleanup
"""
from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from app.orchestration.metrics import get_agent_metrics, get_all_metrics, get_summary
from app.orchestration.session_manager import cleanup_abandoned_sessions, get_session_stats
from app.orchestration.telemetry import get_recent_spans
from services.auth import UserContext, get_current_user

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


@router.get("/metrics")
async def list_metrics(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    """Per-agent performance metrics (latency, success rate, cache hits).

    Returns histograms and counters for all agents that have been invoked
    since the last restart.
    """
    return {
        "agents": get_all_metrics(),
        "summary": get_summary(),
    }


@router.get("/metrics/summary")
async def metrics_summary(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    """High-level system-wide summary (total calls, success rate, flags)."""
    return get_summary()


@router.get("/metrics/{agent_name}")
async def agent_metrics(
    agent_name: str,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    """Metrics for a specific agent."""
    result = get_agent_metrics(agent_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No metrics for agent '{agent_name}'")
    return result


@router.get("/spans")
async def recent_spans(
    user: Annotated[UserContext, Depends(get_current_user)],
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Recent telemetry spans (last N, default 50, max 200).

    Shows the trace of orchestration runs: planner → router → executor → merger.
    Each span includes operation name, duration, status, and agent metadata.
    """
    capped = min(max(limit, 1), 200)
    return get_recent_spans(capped)


@router.get("/sessions")
async def session_stats(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    """Session count statistics — active vs stale per agent.

    Shows how many multi-turn sessions are active vs abandoned (exceeding
    the TTL window). Useful for capacity planning and cleanup monitoring.
    """
    sb = getattr(request.app.state, "supabase", None)
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase unavailable")
    return await get_session_stats(sb)


@router.post("/sessions/cleanup")
async def trigger_cleanup(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    """Manually trigger session cleanup (admin action).

    Deletes abandoned sessions older than the configured TTL (default 72h).
    Normally runs automatically on startup; this endpoint allows on-demand
    cleanup for incident response.
    """
    sb = getattr(request.app.state, "supabase", None)
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase unavailable")

    result = await cleanup_abandoned_sessions(sb)
    return {
        "deleted_count": result.deleted_count,
        "error": result.error,
        "duration_ms": result.duration_ms,
        "cutoff_time": result.cutoff_time,
    }
