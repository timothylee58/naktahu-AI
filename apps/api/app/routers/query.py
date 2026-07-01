"""POST /api/v1/query — SSE streaming endpoint."""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import AsyncGenerator, Optional

import structlog
import weave
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from app.agents.graph import pipeline
from app.middleware.sanitise import sanitise_query
from app.models.state import AgentState
from services.auth import _decode_supabase_jwt

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])

_ANON_RATE = os.environ.get("ANON_RATE_LIMIT", "30/hour")
_AUTH_RATE = os.environ.get("AUTH_RATE_LIMIT", "200/hour")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    session_id: Optional[str] = Field(default=None, max_length=128)
    language: Optional[str] = None

    @field_validator("session_id")
    @classmethod
    def session_id_alphanumeric(cls, v: Optional[str]) -> Optional[str]:
        import re
        if v is not None and not re.match(r"^[\w\-]+$", v):
            raise ValueError("session_id must contain only alphanumeric, hyphens, or underscores")
        return v


def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _extract_user_id(authorization: Optional[str]) -> Optional[str]:
    """Extract the verified sub claim from a Bearer JWT.

    Delegates to the shared, signature-verifying decoder used by the rest of
    the API (services.auth._decode_supabase_jwt) so there is a single source
    of truth for JWT verification. Returns None for missing/malformed/expired/
    invalid-signature tokens — never trusts an unverified payload.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    ctx = _decode_supabase_jwt(token)
    return ctx.user_id if ctx else None


@weave.op()
async def _run_pipeline(
    query: str,
    session_id: str,
    user_id: Optional[str],
) -> dict:
    """Execute the full LangGraph pipeline and return a structured result dict.

    This is the root Weave trace for every query. All agent nodes decorated
    with @weave.op automatically nest as child spans under this call.

    Returns a dict consumed by _sse_generator to stream SSE events.
    """
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

    tokens: list[str] = []
    final_state: AgentState = {}  # type: ignore[assignment]
    t0 = time.monotonic()

    async for mode, data in pipeline.astream(
        inputs, stream_mode=["updates", "custom"]
    ):
        if mode == "custom":
            tokens.append(str(data))
        elif mode == "updates":
            if isinstance(data, dict):
                for _node, update in data.items():
                    if isinstance(update, dict):
                        final_state.update(update)  # type: ignore[typeddict-item]

    latency_ms = round((time.monotonic() - t0) * 1000)
    full_text = "".join(tokens) or final_state.get("streaming_token_buffer", "")

    return {
        "tokens": tokens,
        "final_state": dict(final_state),
        # ── experiment metrics surfaced in the Weave UI ──
        "metrics": {
            "latency_ms": latency_ms,
            "token_count": len(tokens),
            "char_count": len(full_text),
            "confidence": final_state.get("confidence_score", 0.0),
            "domain": final_state.get("domain", "unknown"),
            "language": final_state.get("language", "unknown"),
            "needs_clarification": final_state.get("needs_clarification", False),
            "blocked": final_state.get("error") == "blocked",
            "fallback_used": len(tokens) > 0 and len("".join(tokens[:10])) < 20,
        },
    }


async def _sse_generator(
    query: str,
    session_id: str,
    user_id: Optional[str],
) -> AsyncGenerator[str, None]:
    try:
        result = await _run_pipeline(query, session_id, user_id)
        tokens = result["tokens"]
        final_state = result["final_state"]

        for token in tokens:
            yield _sse("token", {"text": token})

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
        yield _sse("error", {"message": "An error occurred. Please try again."})


@router.post("/query")
async def query_endpoint(
    body: QueryRequest,
    authorization: Optional[str] = Header(default=None),
) -> StreamingResponse:
    user_id = _extract_user_id(authorization)
    rate = _AUTH_RATE if user_id else _ANON_RATE

    clean_query = sanitise_query(body.query)
    session_id = body.session_id or str(uuid.uuid4())

    log.info("query_received", session_id=session_id, user_id=user_id, query_len=len(clean_query))

    return StreamingResponse(
        _sse_generator(clean_query, session_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-RateLimit-Limit": rate,
        },
    )
