"""OrchestratorContext — shared state passed to every agent invocation.

The context object carries everything an agent needs to operate within the
orchestration layer: the user's query, auth context, session lineage, and
any findings already produced by sibling agents. It's immutable from the
agent's perspective — agents read context but write to AgentResult.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from services.auth import UserContext


@dataclass(frozen=True)
class OrchestratorContext:
    """Immutable context passed to each agent invocation.

    Agents receive this to understand:
    - What the user asked (query, language, domain)
    - Who is asking (user context with plan/role)
    - Where in the orchestration graph they sit (session lineage)
    - What sibling agents have already found (shared_findings)
    - Operational constraints (timeout, token budget)
    """

    # The user's original query
    query: str

    # Detected language from router_node (bm, en, zh)
    language: str = "en"

    # Detected or preset domain
    domain: str = "government"

    # The authenticated user (plan, role, id)
    user: Optional[UserContext] = None

    # Session management
    session_id: str = ""
    parent_session_id: Optional[str] = None  # set when this is a sub-agent call
    correlation_id: str = ""  # traces the full multi-agent execution

    # Inter-agent collaboration: findings from sibling agents in this
    # orchestration run. Populated by the orchestrator's executor_node
    # before calling dependent agents.
    shared_findings: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    # Operational constraints
    timeout_seconds: float = 30.0
    max_tokens: int = 1024
    stream: bool = True

    # Agent-specific payload (e.g., compliance-drafter's business_type,
    # study-agent's subject). Kept as a generic dict so the protocol
    # doesn't need to know each agent's schema.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def user_id(self) -> str:
        return self.user.user_id if self.user else ""

    @property
    def user_plan(self) -> str:
        return self.user.plan if self.user else "free"

    @property
    def is_sub_agent_call(self) -> bool:
        return self.parent_session_id is not None
