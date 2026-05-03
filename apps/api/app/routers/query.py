"""POST /api/v1/query — SSE streaming endpoint."""
from __future__ import annotations

import json
import os
from typing import AsyncGenerator, Optional

import structlog
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from app.agents.graph import pipeline
from app.middleware.sanitise import sanitise_query
from app.models.state import AgentState

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])

_ANON_RATE = os.environ.get("ANON_RATE_LIMIT", "30/hour")
_AUTH_RATE = os.environ.get("AUTH_RATE_LIMIT", "200/hour")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    session_id: str = Field(..., min_length=1, max_length=128)
    language: Optional[str] = None

    @field_validator("session_id")
    @classmethod
    def session_id_alphanumeric(cls, v: str) -> str:
        import re
        if not re.match(r"^[\w\-]+$", v):
            raise ValueError("session_id must contain only alphanumeric, hyphens, or underscores")
        return v


def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _extract_user_id(authorization: Optional[str]) -> Optional[str]:
    """Extract sub claim from Bearer JWT — verification is in auth middleware."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        import base64
        token = authorization.split(" ", 1)[1]
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub")
    except Exception:
        return None


async def _sse_generator(
    query: str,
    session_id: str,
    user_id: Optional[str],
) -> AsyncGenerator[str, None]:
    inputs: AgentState = {
        "query": query,
        "session_id": session_id,
        "user_id": user_id,
        "retrieved_chunks": [],
        "citations": [],
        "confidence_score": 0.0,
        "needs_clarification": False,
        "streaming_token_buffer": "",
        "error": None,
    }

    final_state: AgentState = {}  # type: ignore[assignment]

    try:
        async for mode, data in pipeline.astream(
            inputs, stream_mode=["updates", "custom"]
        ):
            if mode == "custom":
                yield _sse("token", {"text": data})
            elif mode == "updates":
                if isinstance(data, dict):
                    for _node, update in data.items():
                        if isinstance(update, dict):
                            final_state.update(update)  # type: ignore[typeddict-item]

        for citation in final_state.get("citations", []):
            yield _sse("citation", dict(citation))

        yield _sse(
            "metadata",
            {
                "confidence": final_state.get("confidence_score", 0.0),
                "domain": final_state.get("domain", "government"),
                "language": final_state.get("language", "en"),
            },
        )

        if final_state.get("needs_clarification") and final_state.get("streaming_token_buffer"):
            yield _sse("token", {"text": final_state["streaming_token_buffer"]})

        yield _sse("done", {})

    except Exception as exc:
        log.error("sse_pipeline_error", error=str(exc), query=query[:80])
        yield _sse("error", {"message": str(exc)})


@router.post("/query")
async def query_endpoint(
    body: QueryRequest,
    authorization: Optional[str] = Header(default=None),
) -> StreamingResponse:
    user_id = _extract_user_id(authorization)
    rate = _AUTH_RATE if user_id else _ANON_RATE

    # Sanitise query text (length already validated by Pydantic)
    clean_query = sanitise_query(body.query)

    log.info("query_received", session_id=body.session_id, user_id=user_id, query_len=len(clean_query))

    return StreamingResponse(
        _sse_generator(clean_query, body.session_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            # Surface rate limit info so the frontend can degrade gracefully
            "X-RateLimit-Limit": rate,
        },
    )
