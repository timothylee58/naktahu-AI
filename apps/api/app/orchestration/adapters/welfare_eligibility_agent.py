"""WelfareEligibilityAgentAdapter — cost-of-living / social assistance scheme matching."""
from __future__ import annotations

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability, AgentResult, AgentStatusEnum

log = structlog.get_logger(__name__)


class WelfareEligibilityAgentAdapter(AgentProtocol):
    """Adapter for the Welfare Eligibility Agent.

    Single-shot: given a complete household profile (demographics,
    household income/dependents, employment/education/housing status),
    deterministically filters madani_scheme rows (structured
    eligibility_rules, not free-text RAG) and returns matched schemes with
    an LLM-written plain-language explanation. See match_node.py — the LLM
    only explains matches already found, never names a scheme itself.
    """

    @property
    def name(self) -> str:
        return "welfare-eligibility-agent"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Matches a household profile against cost-of-living / social assistance schemes (Ihsan MADANI and similar)."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.welfare_knowledge,
            AgentCapability.welfare_matching,
            AgentCapability.single_shot,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["welfare"]

    @property
    def plan_required(self) -> str:
        return "free"

    @property
    def credit_cost(self) -> int:
        return 0

    async def start(self, context: OrchestratorContext) -> AgentResult:
        from app.services.agent_runner import start_welfare_eligibility_agent

        payload = dict(context.extra.get("profile") or {})
        payload["language"] = context.language

        with TimedExecution() as timer:
            try:
                result = await start_welfare_eligibility_agent(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=None,
                )
            except Exception as exc:
                log.error("welfare_eligibility_agent_failed", error=str(exc))
                return make_result(
                    session_id=generate_session_id(),
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        matched = result.get("matched_schemes", [])

        return make_result(
            session_id=result.get("session_id", generate_session_id()),
            agent_name=self.name,
            output=result.get("summary", ""),
            structured_output={
                "matched_schemes": matched,
                "no_schemes_loaded": result.get("no_schemes_loaded", False),
            },
            latency_ms=timer.elapsed_ms,
        )
