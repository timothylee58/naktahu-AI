"""SMEComplianceNavigatorAdapter — PatuhiKu multi-domain compliance checklist."""
from __future__ import annotations

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability, AgentResult, AgentStatusEnum

log = structlog.get_logger(__name__)


class SMEComplianceNavigatorAdapter(AgentProtocol):
    """Adapter for PatuhiKu — the SME Compliance Navigator agent.

    Single-shot: given a free-text business profile (structure, revenue,
    headcount, recent events like a new hire), fans out in parallel to
    tax/payroll/corporate subagents and returns one prioritized, deduped
    compliance checklist with staleness warnings.
    """

    @property
    def name(self) -> str:
        return "sme-compliance-navigator"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "PatuhiKu — cross-references LHDN, EPF/SOCSO/EIS, and SSM compliance obligations for a specific SME."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.compliance_analysis,
            AgentCapability.tax_knowledge,
            AgentCapability.payroll_knowledge,
            AgentCapability.business_knowledge,
            AgentCapability.deadline_tracking,
            AgentCapability.multi_domain_rag,
            AgentCapability.single_shot,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["tax", "payroll", "corporate"]

    @property
    def plan_required(self) -> str:
        return "free"

    @property
    def credit_cost(self) -> int:
        return 1

    async def start(self, context: OrchestratorContext) -> AgentResult:
        """Run the SME Compliance Navigator agent."""
        from app.services.agent_runner import start_sme_compliance_navigator

        payload = {
            "business_profile": context.extra.get("business_profile", context.query),
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                result = await start_sme_compliance_navigator(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=context.extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("sme_compliance_navigator_failed", error=str(exc))
                return make_result(
                    session_id=generate_session_id(),
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        checklist = result.get("checklist", [])
        stale_warnings = result.get("stale_warnings", [])
        summary_lines = [f"[{item['label']}] {item['item']}" for item in checklist]

        return make_result(
            session_id=result.get("session_id", generate_session_id()),
            agent_name=self.name,
            output="\n".join(summary_lines),
            structured_output={
                "checklist": checklist,
                "stale_warnings": stale_warnings,
                "triggered_domains": result.get("triggered_domains", []),
            },
            suggestions=stale_warnings,
            latency_ms=timer.elapsed_ms,
        )
