"""ScamCheckAgentAdapter — pasted SMS/link/phone number verification."""
from __future__ import annotations

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability, AgentResult, AgentStatusEnum

log = structlog.get_logger(__name__)


class ScamCheckAgentAdapter(AgentProtocol):
    """Adapter for ScamShield (the scam-check agent).

    Single-shot: given pasted SMS/message text, deterministically extracts
    any URLs and checks them against official_gov_domains (structured
    lookup + typosquat distance check, not free-text RAG), then has an LLM
    explain the verdict already reached. See check_node.py — the LLM never
    decides whether a domain is official, it only explains a verdict this
    node already found.
    """

    @property
    def name(self) -> str:
        return "scam-check-agent"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Checks a pasted SMS/link/phone number claiming to be from a government agency or bank against a curated list of verified official domains."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.scam_detection,
            AgentCapability.single_shot,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["scam_check"]

    @property
    def plan_required(self) -> str:
        return "free"

    @property
    def credit_cost(self) -> int:
        return 0

    async def start(self, context: OrchestratorContext) -> AgentResult:
        from app.services.agent_runner import start_scam_check_agent

        payload = {
            "input_text": context.extra.get("input_text", ""),
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                result = await start_scam_check_agent(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=None,
                )
            except Exception as exc:
                log.error("scam_check_agent_failed", error=str(exc))
                return make_result(
                    session_id=generate_session_id(),
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        return make_result(
            session_id=result.get("session_id", generate_session_id()),
            agent_name=self.name,
            output=result.get("summary", ""),
            structured_output={
                "checks": result.get("checks", []),
                "overall_verdict": result.get("overall_verdict", "no_url_found"),
                "text_red_flags": result.get("text_red_flags", []),
            },
            latency_ms=timer.elapsed_ms,
        )
