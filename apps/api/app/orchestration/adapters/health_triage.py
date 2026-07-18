"""HealthTriageAdapter — BM symptom intake with KKM facility recommendations."""
from __future__ import annotations

from typing import Optional

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability, AgentResult, AgentStatus, AgentStatusEnum

log = structlog.get_logger(__name__)


class HealthTriageAdapter(AgentProtocol):
    """Adapter for the Health Triage vertical agent.

    Single-shot symptom intake: parses symptoms, queries KKM RAG,
    recommends nearby facilities with disclaimer.
    """

    @property
    def name(self) -> str:
        return "health-triage"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "BM symptom intake with KKM facility recommendations."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.symptom_triage,
            AgentCapability.healthcare_knowledge,
            AgentCapability.conversational_intake,
            AgentCapability.multi_turn,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["healthcare"]

    @property
    def supports_multi_turn(self) -> bool:
        return True

    async def start(self, context: OrchestratorContext) -> AgentResult:
        """Run the health triage agent."""
        from app.services.agent_runner import start_health_triage

        payload = {
            "message": context.query,
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                result = await start_health_triage(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=context.extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("health_triage_failed", error=str(exc))
                return make_result(
                    session_id=generate_session_id(),
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        output = result.get("output", {})
        return make_result(
            session_id=result.get("session_id", generate_session_id()),
            agent_name=self.name,
            output=output.get("response", "") if isinstance(output, dict) else str(output),
            structured_output=output if isinstance(output, dict) else {"raw": output},
            latency_ms=timer.elapsed_ms,
        )

    async def get_status(self, session_id: str) -> AgentStatus:
        """Check health triage session status."""
        from app.agents.checkpointer import get_checkpointer
        from app.services.agent_runner import get_health_status

        result = await get_health_status(session_id, get_checkpointer())
        return AgentStatus(
            session_id=session_id,
            agent_name=self.name,
            status=AgentStatusEnum.completed if result.get("status") != "not_found" else AgentStatusEnum.failed,
        )
