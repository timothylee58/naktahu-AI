"""Orchestration telemetry — structured span tracking for multi-agent runs.

Provides lightweight tracing without requiring the full OpenTelemetry SDK
(which would be a new dependency). Instead, uses structlog + Sentry spans
(already in the stack) plus an in-memory span collector for the metrics
endpoint.

Each orchestration run produces spans:
  orchestration.run        (root — full lifecycle)
    orchestration.plan     (planner_node)
    orchestration.route    (router_node)
    orchestration.execute  (executor — one child per agent)
      agent.{name}         (individual agent invocation)
    orchestration.merge    (merger_node)

Spans are:
1. Emitted to structlog (structured JSON in production → shipped to log backend)
2. Recorded in-memory for /api/v1/orchestration/metrics (last 1000 spans, ring buffer)
3. Attached to Sentry transaction if SENTRY_DSN is configured
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import structlog

log = structlog.get_logger(__name__)

_MAX_SPAN_BUFFER = 1000


@dataclass
class Span:
    """A single telemetry span for orchestration tracking."""

    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_id: Optional[str] = None
    correlation_id: str = ""
    operation: str = ""  # e.g. "orchestration.run", "agent.knowledge-qa"
    agent_name: Optional[str] = None
    task_id: Optional[str] = None
    status: str = "ok"  # ok | error | timeout
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    # Agent-specific metadata
    attributes: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "ok", **attrs: Any) -> None:
        self.end_time = time.monotonic()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        self.attributes.update(attrs)


# ── Global span ring buffer ────────────────────────────────────────────────────

_span_buffer: deque[Span] = deque(maxlen=_MAX_SPAN_BUFFER)


def record_span(span: Span) -> None:
    """Record a completed span to the ring buffer and emit to structlog."""
    _span_buffer.append(span)
    log.info(
        "telemetry_span",
        operation=span.operation,
        agent=span.agent_name,
        task_id=span.task_id,
        status=span.status,
        duration_ms=span.duration_ms,
        correlation_id=span.correlation_id[:8] if span.correlation_id else None,
        **{k: v for k, v in span.attributes.items() if k in (
            "confidence", "complexity", "agents_used", "output_flagged",
            "sub_tasks_count", "parallel_groups",
        )},
    )


def get_recent_spans(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent spans as dicts (for the metrics endpoint)."""
    spans = list(_span_buffer)[-limit:]
    return [
        {
            "span_id": s.span_id,
            "parent_id": s.parent_id,
            "correlation_id": s.correlation_id,
            "operation": s.operation,
            "agent_name": s.agent_name,
            "task_id": s.task_id,
            "status": s.status,
            "duration_ms": s.duration_ms,
            "attributes": s.attributes,
        }
        for s in spans
    ]


def clear_spans() -> None:
    """Clear the span buffer (for testing)."""
    _span_buffer.clear()


# ── Context manager for span creation ──────────────────────────────────────────


@asynccontextmanager
async def trace_span(
    operation: str,
    *,
    correlation_id: str = "",
    parent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    task_id: Optional[str] = None,
) -> AsyncIterator[Span]:
    """Async context manager that creates, times, and records a span.

    Usage:
        async with trace_span("agent.knowledge-qa", correlation_id=cid) as span:
            result = await adapter.start(context)
            span.attributes["confidence"] = result.confidence
    """
    span = Span(
        parent_id=parent_id,
        correlation_id=correlation_id,
        operation=operation,
        agent_name=agent_name,
        task_id=task_id,
        start_time=time.monotonic(),
    )
    try:
        yield span
    except Exception as exc:
        span.finish(status="error", error=str(exc)[:200])
        record_span(span)
        raise
    else:
        if span.end_time == 0.0:
            span.finish()
        record_span(span)
