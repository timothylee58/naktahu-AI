from __future__ import annotations

import json
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
        parts: list[str] = [f"Answer for [{state.domain}]: ", state.query]
        full_response = "".join(parts)
        for part in parts:
            payload = json.dumps({"text": part})
            yield f"event: token\ndata: {payload}\n\n"
        citations: list[Any] = []
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
