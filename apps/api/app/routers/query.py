"""POST /api/v1/query — SSE streaming endpoint."""
from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

import structlog
from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.graph import pipeline
from app.models.state import AgentState

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


class QueryRequest(BaseModel):
    query: str
    session_id: str
    language: Optional[str] = None


def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _extract_user_id(authorization: Optional[str]) -> Optional[str]:
    """Extract sub claim from Bearer JWT if present (no verification here — middleware does that)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        import base64
        token = authorization.split(" ", 1)[1]
        payload_b64 = token.split(".")[1]
        # Pad base64
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
        # stream_mode=["updates","custom"]:
        #   "custom" chunks are raw tokens written by synthesiser_node via get_stream_writer()
        #   "updates" chunks are node-level state diffs (used to capture final state)
        async for mode, data in pipeline.astream(
            inputs, stream_mode=["updates", "custom"]
        ):
            if mode == "custom":
                # data is a raw token string from synthesiser/clarification
                yield _sse("token", {"text": data})
            elif mode == "updates":
                # Merge every node update into our running state snapshot
                if isinstance(data, dict):
                    for _node, update in data.items():
                        if isinstance(update, dict):
                            final_state.update(update)  # type: ignore[typeddict-item]

        # After graph completes, emit citations
        for citation in final_state.get("citations", []):
            yield _sse("citation", dict(citation))

        # Emit metadata
        yield _sse(
            "metadata",
            {
                "confidence": final_state.get("confidence_score", 0.0),
                "domain": final_state.get("domain", "government"),
                "language": final_state.get("language", "en"),
            },
        )

        # Emit clarification message as token if needs_clarification
        # (clarification_node stores the message in streaming_token_buffer)
        if final_state.get("needs_clarification") and final_state.get(
            "streaming_token_buffer"
        ):
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
    log.info("query_received", session_id=body.session_id, user_id=user_id)

    return StreamingResponse(
        _sse_generator(body.query, body.session_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
