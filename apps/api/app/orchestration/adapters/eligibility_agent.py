"""EligibilityAgentAdapter — multi-turn business grant-eligibility matching.

Replaces GrantFinderAdapter (deliberate architecture decision — see PR body).
Multi-turn: intake spans several turns before the graph produces
matched/near-miss grants and a stacking matrix, so orchestrator callers
should expect an `awaiting_hitl`-style continuation via
app.services.agent_runner.continue_eligibility_agent for turns after the
first, or use the dedicated app/routers/eligibility.py SSE endpoints for the
full streamed experience.
"""
from __future__ import annotations

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability, AgentResult, AgentStatusEnum

log = structlog.get_logger(__name__)


class EligibilityAgentAdapter(AgentProtocol):
    """Adapter for the Eligibility Agent vertical agent.

    Multi-turn agent: intake_node asks up to 3 follow-up questions to build a
    business profile, then grant_rag_node + analyst_node match against the
    grant_database and produce a scored, stacking-aware result.
    """

    @property
    def name(self) -> str:
        return "eligibility-agent"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Multi-turn business grant-eligibility matching with scoring, near-miss detection, and stacking analysis."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.grant_matching,
            AgentCapability.government_knowledge,
            AgentCapability.finance_knowledge,
            AgentCapability.conversational_intake,
            AgentCapability.multi_turn,
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
        """Run the eligibility agent's first intake turn."""
        from app.services.agent_runner import start_eligibility_agent

        payload = {
            "business_type": context.extra.get("business_type", ""),
            "sector": context.extra.get("sector", ""),
            "annual_revenue_myr": context.extra.get("annual_revenue_myr"),
            "is_bumiputera": context.extra.get("is_bumiputera"),
            "registered_months": context.extra.get("registered_months"),
            "message": context.query,
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                result = await start_eligibility_agent(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=context.extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("eligibility_agent_failed", error=str(exc))
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
            output=str(output.get("next_question", "")) if isinstance(output, dict) else str(output),
            structured_output=output if isinstance(output, dict) else {"raw": output},
            latency_ms=timer.elapsed_ms,
        )
