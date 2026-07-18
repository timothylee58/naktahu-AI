"""StudyAgentAdapter — SPM past-paper upload with education RAG."""
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


class StudyAgentAdapter(AgentProtocol):
    """Adapter for the Study Agent vertical agent.

    Accepts SPM past papers (PDF or text), extracts questions, explains
    answers using education RAG, and tracks topic mastery.
    """

    @property
    def name(self) -> str:
        return "study-agent"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "SPM past-paper upload with education RAG explanations."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.study_assistance,
            AgentCapability.education_knowledge,
            AgentCapability.document_processing,
            AgentCapability.multi_turn,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["education"]

    @property
    def plan_required(self) -> str:
        return "student"

    @property
    def supports_multi_turn(self) -> bool:
        return True

    async def start(self, context: OrchestratorContext) -> AgentResult:
        """Start a study agent session with a paper or question."""
        from app.services.agent_runner import start_study_agent

        payload = {
            "subject": context.extra.get("subject", "sejarah"),
            "paper_text": context.extra.get("paper_text", ""),
            "document_base64": context.extra.get("document_base64", ""),
            "message": context.query,
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                result = await start_study_agent(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=context.extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("study_agent_start_failed", error=str(exc))
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
            output=output.get("explanation", "") if isinstance(output, dict) else str(output),
            structured_output=output if isinstance(output, dict) else {"raw": output},
            latency_ms=timer.elapsed_ms,
        )

    async def continue_session(
        self,
        session_id: str,
        message: str,
        context: Optional[OrchestratorContext] = None,
    ) -> AgentResult:
        """Continue a study session (ask about specific question)."""
        from app.services.agent_runner import continue_study_agent

        extra = context.extra if context else {}
        payload = {"message": message}
        if extra.get("question_index") is not None:
            payload["question_index"] = extra["question_index"]

        with TimedExecution() as timer:
            try:
                result = await continue_study_agent(
                    session_id=session_id,
                    payload=payload,
                    checkpointer=extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("study_agent_continue_failed", error=str(exc))
                return make_result(
                    session_id=session_id,
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        output = result.get("output", {})
        return make_result(
            session_id=session_id,
            agent_name=self.name,
            output=output.get("explanation", "") if isinstance(output, dict) else str(output),
            structured_output=output if isinstance(output, dict) else {"raw": output},
            latency_ms=timer.elapsed_ms,
        )

    async def get_status(self, session_id: str) -> AgentStatus:
        """Check study agent session status."""
        from app.agents.checkpointer import get_checkpointer
        from app.services.agent_runner import get_study_status

        result = await get_study_status(session_id, get_checkpointer())
        return AgentStatus(
            session_id=session_id,
            agent_name=self.name,
            status=(
                AgentStatusEnum.completed
                if result.get("status") != "not_found"
                else AgentStatusEnum.failed
            ),
        )
