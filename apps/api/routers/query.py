from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Annotated, Any, AsyncIterator, Optional

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_optional_user
from services.history import persist_session_entry

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["query"])

_rag_available = bool(os.environ.get("OPENAI_API_KEY", "").strip())


@dataclass
class AgentState:
    user_id: Optional[str]
    query: str
    language: str
    domain: str


class QueryBody(BaseModel):
    query: str = Field(..., min_length=1)
    language: str = "en"
    domain: str = "general"
    session_id: Optional[str] = None


@router.post("/query")
@apply_query_rate_limit()
async def query_sse(
    request: Request,
    body: QueryBody,
    optional_user: Annotated[Optional[UserContext], Depends(get_optional_user)],
):
    uid = optional_user.user_id if optional_user else None
    state = AgentState(
        user_id=uid,
        query=body.query,
        language=body.language,
        domain=body.domain,
    )

    async def event_stream() -> AsyncIterator[str]:
        citations: list[Any] = []
        full_response = ""

        if _rag_available:
            try:
                from rag.pipeline import run_query

                result = await run_query(question=state.query, language=state.language)
                full_response = result["answer"]
                citations = result.get("sources", [])
                confidence = result.get("confidence", 1.0)

                # Stream the answer word-by-word for UX
                words = full_response.split(" ")
                for i, word in enumerate(words):
                    chunk = word if i == 0 else f" {word}"
                    yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"

                yield (
                    f"event: done\ndata: {json.dumps({'ok': True, 'citations': citations, 'metadata': {'confidence': confidence}})}\n\n"
                )
            except Exception as exc:
                logger.exception("rag_pipeline_failed", error=str(exc))
                yield f"event: error\ndata: {json.dumps({'message': 'RAG pipeline failed'})}\n\n"
                return
        else:
            # Stub: no OpenAI key configured
            stub_parts = [f"[Demo] Answer for [{state.domain}]: ", state.query]
            full_response = "".join(stub_parts)
            for part in stub_parts:
                yield f"event: token\ndata: {json.dumps({'text': part})}\n\n"
            yield f"event: done\ndata: {json.dumps({'ok': True, 'citations': citations})}\n\n"

        if uid:
            try:
                await persist_session_entry(
                    redis_client=request.app.state.redis,
                    supabase_client=request.app.state.supabase,
                    user_id=uid,
                    query=state.query,
                    language=state.language,
                    domain=state.domain,
                    response_text=full_response,
                    citations=citations,
                )
            except Exception as exc:
                logger.exception("history_persist_failed", error=str(exc))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
