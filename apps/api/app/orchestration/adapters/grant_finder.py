"""GrantFinderAdapter — government grant matching for SMEs and students."""
from __future__ import annotations

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability, AgentResult, AgentStatusEnum

log = structlog.get_logger(__name__)


class GrantFinderAdapter(AgentProtocol):
    """Adapter for the Grant Finder vertical agent.

    Single-shot agent: takes user profile (sector, stage, need) and matches
    against government grant knowledge base.
    """

    @property
    def name(self) -> str:
        return "grant-finder"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Government grant matching for SMEs and students."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.grant_matching,
            AgentCapability.government_knowledge,
            AgentCapability.finance_knowledge,
            AgentCapability.single_shot,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["government", "finance", "education"]

    @property
    def plan_required(self) -> str:
        return "free"

    @property
    def credit_cost(self) -> int:
        return 0

    async def start(self, context: OrchestratorContext) -> AgentResult:
        """Run the grant finder agent."""
        from app.services.agent_runner import start_grant_finder

        payload = {
            "sector": context.extra.get("sector", ""),
            "business_stage": context.extra.get("business_stage", "early"),
            "funding_need": context.extra.get("funding_need", context.query),
            "message": context.query,
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                result = await start_grant_finder(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=context.extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("grant_finder_failed", error=str(exc))
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
            output=str(output.get("summary", "")) if isinstance(output, dict) else str(output),
            structured_output=output if isinstance(output, dict) else {"raw": output},
            latency_ms=timer.elapsed_ms,
        )
