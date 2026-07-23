"""ComplianceDrafterAdapter — multi-turn compliance report with HITL checkpoint."""
from __future__ import annotations

from typing import Optional

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability, AgentResult, AgentStatus, AgentStatusEnum

log = structlog.get_logger(__name__)


class ComplianceDrafterAdapter(AgentProtocol):
    """Adapter for the Compliance Drafter vertical agent.

    Multi-domain PDF compliance report for Malaysian businesses. Supports
    multi-turn (context refinement) and human-in-the-loop (preview before
    PDF generation).
    """

    @property
    def name(self) -> str:
        return "compliance-drafter"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Multi-domain PDF compliance report for Malaysian businesses."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.compliance_analysis,
            AgentCapability.tax_knowledge,
            AgentCapability.business_knowledge,
            AgentCapability.epf_knowledge,
            AgentCapability.pdf_generation,
            AgentCapability.multi_domain_rag,
            AgentCapability.human_in_the_loop,
            AgentCapability.multi_turn,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["tax", "business", "epf"]

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
        """Start a new compliance drafter session."""
        from app.services.agent_runner import start_compliance_drafter

        session_id = generate_session_id()
        payload = {
            "business_type": context.extra.get("business_type", "sole_proprietor"),
            "domains": context.extra.get("domains", ["tax", "business", "epf"]),
            "context": context.extra.get("context", context.query),
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                # Get checkpointer and supabase from app state (passed via extra)
                checkpointer = context.extra.get("checkpointer")
                supabase_client = context.extra.get("supabase_client")

                result = await start_compliance_drafter(
                    user_id=context.user_id,
                    user_email=context.extra.get("user_email"),
                    payload=payload,
                    supabase_client=supabase_client,
                    checkpointer=checkpointer,
                )
            except Exception as exc:
                log.error("compliance_drafter_start_failed", error=str(exc))
                return make_result(
                    session_id=session_id,
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        status = AgentStatusEnum.awaiting_input if result.get("awaiting_hitl") else AgentStatusEnum.completed
        return make_result(
            session_id=result.get("session_id", session_id),
            agent_name=self.name,
            status=status,
            output=str(result.get("report_json") or result.get("output", "")),
            structured_output=result.get("output", {}),
            latency_ms=timer.elapsed_ms,
            next_prompt="Review the report preview and confirm to generate PDF." if status == AgentStatusEnum.awaiting_input else None,
        )

    async def continue_session(
        self,
        session_id: str,
        message: str,
        context: Optional[OrchestratorContext] = None,
    ) -> AgentResult:
        """Continue a compliance drafter session with additional context."""
        from app.services.agent_runner import continue_compliance_drafter

        extra = context.extra if context else {}
        payload = {"context": message}
        if extra.get("business_type"):
            payload["business_type"] = extra["business_type"]
        if extra.get("domains"):
            payload["domains"] = extra["domains"]

        with TimedExecution() as timer:
            try:
                result = await continue_compliance_drafter(
                    session_id=session_id,
                    user_id=context.user_id if context else "",
                    payload=payload,
                    checkpointer=extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("compliance_drafter_continue_failed", error=str(exc))
                return make_result(
                    session_id=session_id,
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        return make_result(
            session_id=session_id,
            agent_name=self.name,
            output=str(result.get("report_json") or ""),
            structured_output=result.get("output", {}),
            latency_ms=timer.elapsed_ms,
        )

    async def get_status(self, session_id: str) -> AgentStatus:
        """Check compliance drafter session status."""
        from app.agents.checkpointer import get_checkpointer
        from app.services.agent_runner import get_compliance_status

        result = await get_compliance_status(session_id, get_checkpointer())
        status_map = {
            "awaiting_hitl": AgentStatusEnum.awaiting_input,
            "completed": AgentStatusEnum.completed,
            "not_found": AgentStatusEnum.failed,
        }
        return AgentStatus(
            session_id=session_id,
            agent_name=self.name,
            status=status_map.get(result.get("status", ""), AgentStatusEnum.completed),
            current_step=result.get("status"),
        )
