"""Shared types for the orchestration layer.

These are the standardized data structures all agents produce and the
orchestrator consumes. Designed to be serializable (Pydantic models) so they
can travel over Redis, SSE, and HTTP boundaries without manual conversion.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentStatusEnum(str, Enum):
    """Lifecycle states an agent session can be in."""

    pending = "pending"
    running = "running"
    awaiting_input = "awaiting_input"  # HITL checkpoint
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    timed_out = "timed_out"


class AgentCapability(str, Enum):
    """Declarative capabilities an agent can advertise.

    Used by the orchestrator planner to match sub-tasks to agents without
    needing to know agent internals.
    """

    # Domain knowledge
    tax_knowledge = "tax_knowledge"
    epf_knowledge = "epf_knowledge"
    payroll_knowledge = "payroll_knowledge"
    business_knowledge = "business_knowledge"
    immigration_knowledge = "immigration_knowledge"
    education_knowledge = "education_knowledge"
    healthcare_knowledge = "healthcare_knowledge"
    legal_knowledge = "legal_knowledge"
    government_knowledge = "government_knowledge"
    finance_knowledge = "finance_knowledge"
    culture_knowledge = "culture_knowledge"
    property_knowledge = "property_knowledge"
    welfare_knowledge = "welfare_knowledge"

    # Functional capabilities
    pdf_generation = "pdf_generation"
    multi_domain_rag = "multi_domain_rag"
    conversational_intake = "conversational_intake"
    document_processing = "document_processing"
    deadline_tracking = "deadline_tracking"
    grant_matching = "grant_matching"
    welfare_matching = "welfare_matching"
    symptom_triage = "symptom_triage"
    study_assistance = "study_assistance"
    compliance_analysis = "compliance_analysis"
    scam_detection = "scam_detection"

    # Interaction patterns
    streaming = "streaming"
    multi_turn = "multi_turn"
    human_in_the_loop = "human_in_the_loop"
    single_shot = "single_shot"


class Citation(BaseModel):
    """A single citation returned by an agent."""

    title: str = ""
    ministry: str = ""
    url: str = ""
    confidence: float = 0.0
    stale_disclaimer: bool = False
    # ISO date the cited rule/figure takes effect. Mirrors the same field on
    # app.models.state.Citation so a citation crossing the orchestration
    # boundary keeps its date instead of degrading to a bare staleness bool.
    effective_date: Optional[str] = None


class AgentResult(BaseModel):
    """Standardized result from any agent execution.

    Every agent adapter must return this, regardless of whether the
    underlying agent is a LangGraph graph, a simple function, or an
    external API call.
    """

    session_id: str
    agent_name: str
    status: AgentStatusEnum = AgentStatusEnum.completed
    output: str = ""
    structured_output: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    suggestions: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    # Metadata for orchestrator decisions
    tokens_used: int = 0
    latency_ms: float = 0.0
    cache_hit: bool = False
    output_flagged: bool = False
    # For multi-turn agents
    next_prompt: Optional[str] = None
    awaiting_fields: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentStatus(BaseModel):
    """Lightweight status check response (no full output)."""

    session_id: str
    agent_name: str
    status: AgentStatusEnum
    progress_pct: Optional[float] = None  # 0.0 – 1.0
    current_step: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SubTask(BaseModel):
    """A decomposed piece of a complex query assigned to an agent."""

    task_id: str
    description: str
    target_agent: str
    priority: int = 0  # lower = higher priority
    depends_on: list[str] = Field(default_factory=list)  # task_ids
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: AgentStatusEnum = AgentStatusEnum.pending
    result: Optional[AgentResult] = None
