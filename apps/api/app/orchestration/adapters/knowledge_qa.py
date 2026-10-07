"""KnowledgeQAAdapter — wraps the main LangGraph pipeline (graph.py).

This is the core Q&A pipeline: router → guard → rag → analyst → synthesiser.
It's the only adapter that supports true token-by-token streaming via the
SSE contract.
"""
from __future__ import annotations

from typing import AsyncIterator

import structlog

from app.orchestration.adapters.base import TimedExecution, generate_session_id, make_result
from app.orchestration.context import OrchestratorContext
from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability, AgentResult, AgentStatusEnum

log = structlog.get_logger(__name__)


class KnowledgeQAAdapter(AgentProtocol):
    """Adapter for the main NakTahu Q&A pipeline.

    Wraps app.agents.graph.pipeline (router→guard→rag→analyst→synthesiser).
    Supports streaming. Does not support multi-turn (each query is stateless).
    """

    @property
    def name(self) -> str:
        return "knowledge-qa"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "General Malaysian civic knowledge Q&A with bilingual streaming answers."

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability.government_knowledge,
            AgentCapability.education_knowledge,
            AgentCapability.legal_knowledge,
            AgentCapability.finance_knowledge,
            AgentCapability.healthcare_knowledge,
            AgentCapability.tax_knowledge,
            AgentCapability.epf_knowledge,
            AgentCapability.business_knowledge,
            AgentCapability.immigration_knowledge,
            AgentCapability.culture_knowledge,
            AgentCapability.streaming,
            AgentCapability.single_shot,
        ]

    @property
    def supported_domains(self) -> list[str]:
        return [
            "government", "education", "legal", "finance",
            "healthcare", "epf", "tax", "business", "immigration", "culture",
        ]

    @property
    def supports_streaming(self) -> bool:
        return True

    async def start(self, context: OrchestratorContext) -> AgentResult:
        """Run the full pipeline synchronously (non-streaming mode).

        For streaming, callers should use stream() instead.
        """
        from app.agents.graph import compile_pipeline
        from app.models.state import AgentState

        session_id = context.session_id or generate_session_id()

        initial_state: AgentState = {
            "query": context.query,
            "language": context.language,
            "domain": context.domain,
            "session_id": session_id,
            "user_id": context.user_id,
        }

        with TimedExecution() as timer:
            try:
                pipeline = compile_pipeline()
                result = await pipeline.ainvoke(initial_state)
            except Exception as exc:
                log.error("knowledge_qa_failed", error=str(exc), query=context.query[:80])
                return make_result(
                    session_id=session_id,
                    agent_name=self.name,
                    status=AgentStatusEnum.failed,
                    error=str(exc),
                )

        output = result.get("streaming_token_buffer", "")
        citations = []
        for c in result.get("citations", []):
            if hasattr(c, "title"):
                citations.append({
                    "title": c.title,
                    "ministry": c.ministry,
                    "url": c.url,
                    "confidence": c.confidence,
                    "stale_disclaimer": c.stale_disclaimer,
                    "effective_date": getattr(c, "effective_date", None),
                })
            elif isinstance(c, dict):
                citations.append(c)

        return make_result(
            session_id=session_id,
            agent_name=self.name,
            output=output,
            citations=citations,
            confidence=result.get("confidence_score", 0.0),
            suggestions=result.get("suggestions", []),
            latency_ms=timer.elapsed_ms,
            output_flagged=result.get("output_flagged", False),
        )

    async def stream(self, context: OrchestratorContext) -> AsyncIterator[str]:
        """Stream tokens from the synthesis stage via the public stream_synthesis."""
        from app.agents.synthesiser_node import stream_synthesis
        from app.models.state import AgentState

        # Build state after routing (for streaming, we need at least the
        # router and rag stages to have run). For the orchestrator's streaming
        # path, we run the non-streaming nodes first, then stream synthesis.
        from app.agents.analyst_node import analyst_node
        from app.agents.guard_node import guard_node
        from app.agents.rag_node import rag_node
        from app.agents.router_node import router_node

        state: AgentState = {
            "query": context.query,
            "language": context.language,
            "domain": context.domain,
            "session_id": context.session_id or generate_session_id(),
            "user_id": context.user_id,
        }

        # Run pre-synthesis nodes
        router_result = await router_node(state)
        state.update(router_result)

        # Guard check — if blocked, yield refusal
        guard_result = await guard_node(state)
        if guard_result.get("error") == "blocked":
            yield guard_result.get("streaming_token_buffer", "")
            return
        state.update(guard_result)

        rag_result = await rag_node(state)
        state.update(rag_result)

        analyst_result = await analyst_node(state)
        state.update(analyst_result)

        if state.get("needs_clarification"):
            lang = state.get("language", "en")
            if lang == "bm":
                yield (
                    "Maaf, saya tidak pasti dengan jawapan untuk soalan anda. "
                    "Boleh anda berikan lebih maklumat atau nyatakan soalan dengan lebih jelas?"
                )
            else:
                yield (
                    "I'm not confident enough to answer this question accurately. "
                    "Could you please provide more context or rephrase your question?"
                )
            return

        # Stream synthesis tokens
        async for token in stream_synthesis(state):
            yield token
