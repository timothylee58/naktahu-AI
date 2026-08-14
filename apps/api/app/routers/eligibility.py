"""app/routers/eligibility.py — dedicated SSE router for the Eligibility Agent.

POST /api/v1/eligibility/start
  Creates a new eligibility session. Returns SSE stream with the first
  intake question.

POST /api/v1/eligibility/message
  Submits a user turn. SSE stream:
  - Turns 0-2: intake_node asks follow-up questions ('question' event)
  - Once intake_complete: full grant RAG + analyst + synthesiser pipeline
    runs and streams the grant summary ('token'/'grant'/'stacking'/'metadata' events)

GET /api/v1/eligibility/{session_id}/result
  Non-streaming: returns the final matched_grants JSON for UI grant cards.

SSE event types: question, token, grant, stacking, metadata, done, error.

Mounted in BOTH apps/api/main.py and apps/api/app/main.py per Trap #1.
Supabase-null guards everywhere per Trap #4 — no Depends(get_supabase);
this repo's Supabase client lives on request.app.state.supabase.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, AsyncGenerator, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.agents.checkpointer import get_checkpointer
from app.agents.eligibility_agent.compatibility import grant_compatibility_check
from app.agents.eligibility_agent.graph import get_eligibility_agent_graph
from app.agents.eligibility_agent.state import EligibilityState
from app.agents.eligibility_agent.synthesiser_node import synthesiser_node
from app.agents.runtime import thread_config as _thread_config
from routers._request_fields import Language, normalise_language
from services.auth import UserContext, get_optional_user

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/eligibility", tags=["eligibility"])


# ── Request / Response models (bounded fields per CLAUDE.md hard rule) ────────
class StartRequest(BaseModel):
    language: Optional[Language] = None


class MessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128, pattern=r"^[\w\-]+$")
    message: str = Field(..., min_length=1, max_length=2000)
    language: Optional[Language] = None


class SessionResult(BaseModel):
    session_id: str
    status: str
    matched_grants: list[dict[str, Any]]
    near_miss_grants: list[dict[str, Any]]
    stacking_matrix: Optional[dict[str, Any]]
    business_profile: Optional[dict[str, Any]]


class CompatibilityRequest(BaseModel):
    programme_names: list[str] = Field(..., min_length=2, max_length=10)
    language: Language = "en"

    @field_validator("programme_names")
    @classmethod
    def _bound_items(cls, v: list[str]) -> list[str]:
        for name in v:
            if not (1 <= len(name.strip()) <= 200):
                raise ValueError("each programme name must be 1-200 characters")
        return v

    @field_validator("language")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_language(v)


class CompatibilityPair(BaseModel):
    programme_a: str = Field(..., max_length=200)
    programme_b: str = Field(..., max_length=200)
    verdict: Literal["stackable", "partial_overlap", "conflict", "unknown"]
    overlap_scope: Optional[str] = Field(None, max_length=64)
    explanation: str = Field("", max_length=4000)
    source_url: Optional[str] = Field(None, max_length=500)
    last_verified: Optional[str] = Field(None, max_length=32)
    source: Literal["rules_table", "legacy_array", "none"]


class CompatibilityResponse(BaseModel):
    programmes: list[str] = Field(..., max_length=10)
    pairs: list[CompatibilityPair] = Field(..., max_length=45)
    has_conflicts: bool
    conflict_count: int = Field(..., ge=0, le=45)
    partial_overlap_count: int = Field(..., ge=0, le=45)
    stackable_count: int = Field(..., ge=0, le=45)
    unknown_count: int = Field(..., ge=0, le=45)
    unrecognised_programmes: list[str] = Field(default_factory=list, max_length=10)
    advice: list[str] = Field(default_factory=list, max_length=10)
    degraded: bool = False
    language: Literal["bm", "en"] = "en"


def _checkpointer(request: Request) -> Any:
    return getattr(request.app.state, "checkpointer", None) or get_checkpointer()



async def _sse_stream(generator: AsyncGenerator[dict[str, Any], None]) -> AsyncGenerator[str, None]:
    """Serialise dict events as SSE text/event-stream format."""
    async for event in generator:
        event_type = event.get("type", "token")
        data = {k: v for k, v in event.items() if k != "type"}
        yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/start")
async def start_session(
    body: StartRequest,
    request: Request,
    user: Optional[UserContext] = Depends(get_optional_user),
) -> StreamingResponse:
    """Create a new eligibility session and emit the first intake question."""
    supabase = getattr(request.app.state, "supabase", None)
    if not supabase:
        raise HTTPException(status_code=503, detail="Eligibility Agent is temporarily unavailable.")

    session_id = str(uuid.uuid4())
    language = normalise_language(body.language) if body.language else "bm"

    graph = get_eligibility_agent_graph(checkpointer=_checkpointer(request))
    initial_state: EligibilityState = {
        "session_id": session_id,
        "user_id": user.user_id if user else None,
        "language": language,
        "current_turn": 0,
        "messages": [],
        "latest_user_input": "",
        "business_profile": None,
        "intake_complete": False,
        "needs_more_info": True,
        "needs_clarification": False,
    }

    try:
        await graph.ainvoke(initial_state, config=_thread_config(session_id, supabase=supabase))
        snapshot = await graph.aget_state(_thread_config(session_id))
        result_state = dict(snapshot.values) if snapshot else initial_state
    except Exception as exc:
        log.error("eligibility_start_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Eligibility Agent is temporarily unavailable.") from exc

    try:
        supabase.table("eligibility_sessions").insert({
            "session_id": session_id,
            "user_id": user.user_id if user else None,
            "status": "intake",
            "current_turn": result_state.get("current_turn", 1),
        }).execute()
    except Exception as exc:
        log.warning("eligibility_session_persist_failed", error=str(exc))

    async def _emit_question() -> AsyncGenerator[dict[str, Any], None]:
        yield {"type": "question", "text": result_state.get("next_question", ""), "session_id": session_id}
        yield {"type": "done"}

    return StreamingResponse(
        _sse_stream(_emit_question()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Session-Id": session_id},
    )


@router.post("/message")
async def send_message(
    body: MessageRequest,
    request: Request,
    user: Optional[UserContext] = Depends(get_optional_user),
) -> StreamingResponse:
    """Submit a user turn. Intake turns emit a question; once intake is
    complete, the full grant RAG + analyst + synthesiser pipeline streams
    the grant summary."""
    supabase = getattr(request.app.state, "supabase", None)
    if not supabase:
        raise HTTPException(status_code=503, detail="Eligibility Agent is temporarily unavailable.")

    graph = get_eligibility_agent_graph(checkpointer=_checkpointer(request))
    thread = _thread_config(body.session_id)

    snapshot = await graph.aget_state(thread)
    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail="Session not found")

    language = normalise_language(body.language) if body.language else snapshot.values.get("language", "bm")

    try:
        await graph.aupdate_state(thread, {
            "latest_user_input": body.message,
            "language": language,
        })
        await graph.ainvoke(None, config=_thread_config(body.session_id, supabase=supabase))
        snapshot = await graph.aget_state(thread)
        result_state = dict(snapshot.values) if snapshot else {}
    except Exception as exc:
        log.error("eligibility_message_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Eligibility Agent is temporarily unavailable.") from exc

    new_status = "matching" if result_state.get("intake_complete") else "intake"
    profile = result_state.get("business_profile") or {}
    try:
        supabase.table("eligibility_sessions").update({
            "current_turn": result_state.get("current_turn", 0),
            "status": new_status,
            "business_type": profile.get("business_type"),
            "sector": profile.get("sector"),
            "annual_revenue_myr": profile.get("annual_revenue_myr"),
            "is_bumiputera": profile.get("is_bumiputera"),
            "registered_months": profile.get("registered_months"),
        }).eq("session_id", body.session_id).execute()
    except Exception as exc:
        log.warning("eligibility_session_update_failed", error=str(exc))

    if result_state.get("needs_more_info"):
        question = result_state.get("next_question", "")

        async def _emit_question() -> AsyncGenerator[dict[str, Any], None]:
            yield {"type": "question", "text": question}
            yield {"type": "done"}

        return StreamingResponse(_sse_stream(_emit_question()), media_type="text/event-stream")

    async def _emit_grants() -> AsyncGenerator[dict[str, Any], None]:
        async for event in synthesiser_node(result_state):
            yield event

        try:
            supabase.table("eligibility_sessions").update({
                "matched_grants": result_state.get("matched_grants") or [],
                "status": "completed",
            }).eq("session_id", body.session_id).execute()
        except Exception as exc:
            log.warning("eligibility_session_finalise_failed", error=str(exc))

    return StreamingResponse(_sse_stream(_emit_grants()), media_type="text/event-stream")


@router.post("/compatibility", response_model=CompatibilityResponse)
async def check_compatibility(
    body: CompatibilityRequest,
    request: Request,
    user: Optional[UserContext] = Depends(get_optional_user),
) -> CompatibilityResponse:
    """Grant stacking compatibility matrix for 2-10 programmes.

    Synchronous JSON lookup (not SSE) — usable directly from the UI without
    running a full intake session. Auth tier matches the sibling eligibility
    endpoints (get_optional_user): this is public-value reference data.
    No slowapi decorator here for the same reason the sibling endpoints have
    none; the global middleware rate limiter still applies.
    """
    supabase = getattr(request.app.state, "supabase", None)
    if not supabase:
        raise HTTPException(status_code=503, detail="Eligibility Agent is temporarily unavailable.")

    result = await grant_compatibility_check(
        body.programme_names, supabase, language=body.language
    )
    log.info(
        "grant_compatibility_checked",
        n=len(result["programmes"]),
        conflicts=result["conflict_count"],
        degraded=result["degraded"],
        authed=bool(user),
    )
    return CompatibilityResponse(**result)


@router.get("/{session_id}/result", response_model=SessionResult)
async def get_result(
    session_id: str,
    request: Request,
    user: Optional[UserContext] = Depends(get_optional_user),
) -> SessionResult:
    """Return final structured grant results for a completed session."""
    supabase = getattr(request.app.state, "supabase", None)
    if not supabase:
        raise HTTPException(status_code=503, detail="Eligibility Agent is temporarily unavailable.")

    checkpointer = _checkpointer(request)
    graph = get_eligibility_agent_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail="Session not found")

    values = dict(snapshot.values)
    return SessionResult(
        session_id=session_id,
        status="completed" if values.get("intake_complete") else "intake",
        matched_grants=values.get("matched_grants") or [],
        near_miss_grants=values.get("near_miss_grants") or [],
        stacking_matrix=values.get("stacking_matrix"),
        business_profile=values.get("business_profile"),
    )
