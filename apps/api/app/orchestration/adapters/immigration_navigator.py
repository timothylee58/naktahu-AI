"""ImmigrationNavigatorAdapter — multi-turn visa intake with immigration RAG."""
from __future__ import annotations

from typing import Optional

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import (
    AgentCapability,
    AgentResult,
    AgentStatus,
    AgentStatusEnum,
)

log = structlog.get_logger(__name__)


class ImmigrationNavigatorAdapter(AgentProtocol):
    """Adapter for the Immigration Navigator vertical agent.

    Multi-turn conversational intake that collects visa requirements
    and queries immigration RAG for tailored guidance.
    """

    @property
    def name(self) -> str:
        return "immigration-navigator"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Conversational visa intake with immigration RAG."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.immigration_knowledge,
            AgentCapability.conversational_intake,
            AgentCapability.multi_turn,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["immigration"]

    @property
    def plan_required(self) -> str:
        return "free"

    @property
    def credit_cost(self) -> int:
        return 1

    @property
    def supports_multi_turn(self) -> bool:
        return True

    async def start(self, context: OrchestratorContext) -> AgentResult:
        """Start a new immigration navigator session."""
        from app.services.agent_runner import start_immigration_navigator

        payload = {
            "message": context.query,
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                result = await start_immigration_navigator(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=context.extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("immigration_navigator_start_failed", error=str(exc))
                return make_result(
                    session_id=generate_session_id(),
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        status_str = result.get("status", "completed")
        status = (
            AgentStatusEnum.awaiting_input
            if status_str == "needs_input"
            else AgentStatusEnum.completed
        )

        output = result.get("output", {})
        return make_result(
            session_id=result.get("session_id", generate_session_id()),
            agent_name=self.name,
            status=status,
            output=output.get("response", "") if isinstance(output, dict) else str(output),
            structured_output=output if isinstance(output, dict) else {"raw": output},
            latency_ms=timer.elapsed_ms,
            next_prompt=result.get("next_prompt"),
        )

    async def continue_session(
        self,
        session_id: str,
        message: str,
        context: Optional[OrchestratorContext] = None,
    ) -> AgentResult:
        """Continue an immigration navigator session with user response."""
        from app.services.agent_runner import continue_immigration_navigator

        extra = context.extra if context else {}
        payload = {"message": message}

        with TimedExecution() as timer:
            try:
                result = await continue_immigration_navigator(
                    session_id=session_id,
                    payload=payload,
                    supabase_client=extra.get("supabase_client"),
                    checkpointer=extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("immigration_navigator_continue_failed", error=str(exc))
                return make_result(
                    session_id=session_id,
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        status_str = result.get("status", "completed")
        status = (
            AgentStatusEnum.awaiting_input
            if status_str == "needs_input"
            else AgentStatusEnum.completed
        )
        output = result.get("output", {})
        return make_result(
            session_id=session_id,
            agent_name=self.name,
            status=status,
            output=output.get("response", "") if isinstance(output, dict) else str(output),
            structured_output=output if isinstance(output, dict) else {"raw": output},
            latency_ms=timer.elapsed_ms,
            next_prompt=result.get("next_prompt"),
        )

    async def get_status(self, session_id: str) -> AgentStatus:
        """Check immigration navigator session status."""
        from app.agents.checkpointer import get_checkpointer
        from app.services.agent_runner import get_immigration_status

        result = await get_immigration_status(session_id, get_checkpointer())
        status_map = {
            "needs_input": AgentStatusEnum.awaiting_input,
            "completed": AgentStatusEnum.completed,
            "not_found": AgentStatusEnum.failed,
        }
        return AgentStatus(
            session_id=session_id,
            agent_name=self.name,
            status=status_map.get(result.get("status", ""), AgentStatusEnum.completed),
        )
