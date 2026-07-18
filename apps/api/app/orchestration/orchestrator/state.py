"""OrchestratorState — TypedDict flowing through the SuperGraph.

This defines all state that the orchestrator nodes read/write as the
query progresses from planning through execution to final synthesis.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional

from typing_extensions import TypedDict


class SubTaskState(TypedDict, total=False):
    """A single sub-task as decided by the planner."""

    task_id: str
    description: str
    target_agent: str
    domain: str
    capabilities_needed: list[str]
    priority: int  # lower = higher priority
    depends_on: list[str]  # task_ids this depends on
    status: str  # pending | running | completed | failed
    result: Optional[dict[str, Any]]


class AgentExecutionResult(TypedDict, total=False):
    """Result from a single agent execution within the orchestrator."""

    task_id: str
    agent_name: str
    status: str
    output: str
    structured_output: dict[str, Any]
    citations: list[dict[str, Any]]
    confidence: float
    suggestions: list[str]
    error: Optional[str]
    latency_ms: float
    output_flagged: bool


class OrchestratorState(TypedDict, total=False):
    """Full state for the Orchestrator SuperGraph.

    Flows: planner → router → executor (parallel) → merger → END

    The Annotated[list, operator.add] pattern allows executor fan-out nodes
    to append results without overwriting each other (LangGraph's reducer).
    """

    # ── Input (set by the SSE endpoint before graph invocation) ────────────
    query: str
    language: str  # bm | en | zh
    domain: str  # preset domain hint (optional)
    user_id: str
    user_plan: str  # free | student | pro | business
    user_email: Optional[str]
    session_id: str  # orchestration-level session
    correlation_id: str  # for context bus / tracing

    # ── Planner output ─────────────────────────────────────────────────────
    complexity: str  # simple | moderate | complex
    reasoning: str  # planner's explanation of its decomposition
    sub_tasks: list[SubTaskState]
    # If simple, the planner routes directly to the fast path (knowledge-qa)
    fast_path_agent: Optional[str]

    # ── Router output ──────────────────────────────────────────────────────
    execution_plan: list[SubTaskState]  # sub_tasks with target_agent assigned
    parallel_groups: list[list[str]]  # [[task_ids that can run in parallel], ...]

    # ── Executor output (uses operator.add reducer for parallel writes) ────
    agent_results: Annotated[list[AgentExecutionResult], operator.add]

    # ── Merger output ──────────────────────────────────────────────────────
    final_output: str
    merged_citations: list[dict[str, Any]]
    overall_confidence: float
    suggestions: list[str]
    agents_used: list[str]
    total_latency_ms: float
    output_flagged: bool
