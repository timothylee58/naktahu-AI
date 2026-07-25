"""ResearchSynthesiserAdapter — parallel multi-domain RAG synthesis."""
from __future__ import annotations

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import (
    AgentCapability,
    AgentResult,
    AgentStatusEnum,
)

log = structlog.get_logger(__name__)


class ResearchSynthesiserAdapter(AgentProtocol):
    """Adapter for the Research Synthesiser agent.

    Single-shot: fans out to multiple RAG domains in parallel and merges
    citations. Business-tier only.
    """

    @property
    def name(self) -> str:
        return "research-synthesiser"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Parallel multi-domain RAG synthesis across government, finance, and legal."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.multi_domain_rag,
            AgentCapability.government_knowledge,
            AgentCapability.finance_knowledge,
            AgentCapability.legal_knowledge,
            AgentCapability.education_knowledge,
            AgentCapability.single_shot,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return ["government", "finance", "legal", "education"]

    @property
    def plan_required(self) -> str:
        return "business"

    async def start(self, context: OrchestratorContext) -> AgentResult:
        """Run parallel multi-domain RAG synthesis."""
        from app.services.agent_runner import start_research_synthesiser

        payload = {
            "query": context.query,
            "language": context.language,
        }

        with TimedExecution() as timer:
            try:
                result = await start_research_synthesiser(
                    user_id=context.user_id,
                    payload=payload,
                    supabase_client=context.extra.get("supabase_client"),
                    checkpointer=context.extra.get("checkpointer"),
                )
            except Exception as exc:
                log.error("research_synthesiser_failed", error=str(exc))
                return make_result(
                    session_id=generate_session_id(),
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                    latency_ms=timer.elapsed_ms,
                )

        citations = result.get("citations", [])
        return make_result(
            session_id=result.get("session_id", generate_session_id()),
            agent_name=self.name,
            output=str(result.get("output", "")),
            structured_output={
                "detected_domains": result.get("detected_domains", []),
                "citations": citations,
            },
            citations=citations,
            latency_ms=timer.elapsed_ms,
        )
