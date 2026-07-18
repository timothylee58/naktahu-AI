"""Base utilities shared across agent adapters."""
from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from app.orchestration.context import OrchestratorContext
from app.orchestration.types import AgentResult, AgentStatusEnum

log = structlog.get_logger(__name__)


def generate_session_id() -> str:
    """Generate a new session UUID."""
    return str(uuid.uuid4())


def make_result(
    *,
    session_id: str,
    agent_name: str,
    status: AgentStatusEnum = AgentStatusEnum.completed,
    output: str = "",
    structured_output: dict[str, Any] | None = None,
    citations: list[dict[str, Any]] | None = None,
    confidence: float = 0.0,
    suggestions: list[str] | None = None,
    error: str | None = None,
    tokens_used: int = 0,
    latency_ms: float = 0.0,
    next_prompt: str | None = None,
    awaiting_fields: list[str] | None = None,
    output_flagged: bool = False,
) -> AgentResult:
    """Construct an AgentResult with sensible defaults."""
    from app.orchestration.types import Citation

    parsed_citations = []
    if citations:
        for c in citations:
            if isinstance(c, dict):
                parsed_citations.append(Citation(
                    title=c.get("title", ""),
                    ministry=c.get("ministry", ""),
                    url=c.get("url", ""),
                    confidence=float(c.get("confidence", 0.0)),
                    stale_disclaimer=c.get("stale_disclaimer", False),
                ))
            elif isinstance(c, Citation):
                parsed_citations.append(c)

    return AgentResult(
        session_id=session_id,
        agent_name=agent_name,
        status=status,
        output=output,
        structured_output=structured_output or {},
        citations=parsed_citations,
        confidence=confidence,
        suggestions=suggestions or [],
        error=error,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        next_prompt=next_prompt,
        awaiting_fields=awaiting_fields or [],
        output_flagged=output_flagged,
    )


class TimedExecution:
    """Context manager that tracks execution time in milliseconds."""

    def __init__(self) -> None:
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "TimedExecution":
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed_ms = round((time.monotonic() - self._start) * 1000, 1)
