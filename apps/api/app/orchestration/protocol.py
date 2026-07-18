"""AgentProtocol — the abstract interface every agent adapter implements.

This is the contract between the orchestrator and individual agents. By
implementing this protocol, any agent (LangGraph graph, simple function,
external API) becomes orchestratable — the orchestrator treats them
uniformly regardless of internal implementation.

Design principles:
- Adapters wrap existing agent code without modifying it
- The protocol is async-first (all I/O operations are async)
- Each method has a clear lifecycle meaning
- The protocol supports both single-shot and multi-turn agents
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from app.orchestration.context import OrchestratorContext
from app.orchestration.types import (
    AgentCapability,
    AgentResult,
    AgentStatus,
    AgentStatusEnum,
)


class AgentProtocol(ABC):
    """Abstract base class for all orchestratable agents.

    Subclass this for each vertical agent adapter. The orchestrator calls
    these methods without knowing the agent's internal implementation.

    Required overrides:
        - name, version, description (properties)
        - capabilities (property returning list of AgentCapability)
        - start() — begin a new agent session

    Optional overrides (for multi-turn agents):
        - continue_session() — advance an existing session
        - get_status() — check session lifecycle state
        - cancel() — abort a running session
        - stream() — yield tokens for SSE streaming
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier (matches registry name)."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version string (e.g., '1.0.0').

        Used by the session manager to detect code/state version mismatches
        when resuming checkpointed multi-turn sessions.
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this agent does."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[AgentCapability]:
        """Declarative list of what this agent can do.

        The orchestrator's planner uses these to match sub-tasks to agents
        without needing to understand each agent's internals.
        """
        ...

    @property
    def supported_domains(self) -> list[str]:
        """RAG domains this agent can query. Defaults to empty (general)."""
        return []

    @property
    def plan_required(self) -> str:
        """Minimum plan tier required to use this agent."""
        return "free"

    @property
    def credit_cost(self) -> int:
        """Number of agent credits consumed per completed invocation."""
        return 0

    @property
    def supports_multi_turn(self) -> bool:
        """Whether this agent supports continue_session()."""
        return False

    @property
    def supports_streaming(self) -> bool:
        """Whether this agent supports token-by-token streaming."""
        return False

    @abstractmethod
    async def start(self, context: OrchestratorContext) -> AgentResult:
        """Begin a new agent session.

        For single-shot agents, this returns the complete result.
        For multi-turn agents, this returns the first response (possibly
        with status=awaiting_input and next_prompt set).

        Args:
            context: The orchestrator context with query, user, constraints.

        Returns:
            AgentResult with the agent's output and metadata.
        """
        ...

    async def continue_session(
        self,
        session_id: str,
        message: str,
        context: Optional[OrchestratorContext] = None,
    ) -> AgentResult:
        """Advance an existing multi-turn session.

        Default implementation raises NotImplementedError. Override for
        agents that support conversational flows (compliance-drafter,
        immigration-navigator).

        Args:
            session_id: The session to continue.
            message: The user's follow-up message.
            context: Optional updated context (user might have changed language).

        Returns:
            AgentResult with the next response.
        """
        raise NotImplementedError(f"{self.name} does not support multi-turn sessions")

    async def get_status(self, session_id: str) -> AgentStatus:
        """Check the lifecycle state of an agent session.

        Default implementation returns a generic unknown status.
        Override for agents with stateful sessions.
        """
        return AgentStatus(
            session_id=session_id,
            agent_name=self.name,
            status=AgentStatusEnum.completed,
        )

    async def cancel(self, session_id: str) -> None:
        """Abort a running or awaiting-input session.

        Default implementation is a no-op. Override for agents that need
        to clean up resources (e.g., delete partial PDFs, release checkpointer
        state).
        """
        pass

    async def stream(self, context: OrchestratorContext) -> AsyncIterator[str]:
        """Yield tokens for SSE streaming.

        Default implementation runs start() and yields the full output as
        a single chunk. Override for agents that support true token-by-token
        streaming (e.g., the knowledge Q&A pipeline).
        """
        result = await self.start(context)
        if result.output:
            yield result.output

    def can_handle(self, query: str, domain: str, capabilities_needed: list[AgentCapability]) -> float:
        """Score how well this agent can handle a given task (0.0–1.0).

        Used by the orchestrator's router to rank candidate agents. Default
        implementation checks domain overlap and capability coverage.

        Args:
            query: The user query or sub-task description.
            domain: The target domain.
            capabilities_needed: What the task requires.

        Returns:
            Confidence score 0.0–1.0 (0 = cannot handle, 1 = perfect match).
        """
        score = 0.0

        # Domain match
        if domain in self.supported_domains:
            score += 0.4

        # Capability coverage
        if capabilities_needed:
            matched = sum(1 for c in capabilities_needed if c in self.capabilities)
            score += 0.6 * (matched / len(capabilities_needed))

        return min(score, 1.0)
