from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from middleware.plan_gate import require_plan
from middleware.rate_limit import apply_query_rate_limit
from routers._request_fields import Domain, Language, normalise_language
from services.auth import UserContext, get_current_user
from services.history import (
    delete_session_entry,
    fetch_agent_run_history,
    fetch_history_entries,
    persist_session_entry,
    rename_session_entry,
)

router = APIRouter(prefix="/api/v1", tags=["history"])


class HistoryRenamePayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)


class AgentRunEntryResponse(BaseModel):
    id: str
    agent_name: str
    session_id: Optional[str] = None
    output: dict[str, Any] = Field(default_factory=dict)
    completion_status: str
    turns_count: int = 0
    created_at: str


class HistoryEntryPayload(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    language: Language = "en"
    domain: Domain = "general"
    response_summary: str = Field(..., max_length=150)
    citations: list[Any] = Field(default_factory=list, max_length=100)

    @field_validator("language")
    @classmethod
    def _normalise_language(cls, v: Language) -> Language:
        return normalise_language(v)


@router.get("/history")
@apply_query_rate_limit()
async def get_history(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(require_plan("pro"))],
):
    redis_client = getattr(request.app.state, "redis", None)
    supabase_client = getattr(request.app.state, "supabase", None)
    entries = await fetch_history_entries(redis_client, supabase_client, user.user_id)
    return entries


@router.post("/history", status_code=201)
@apply_query_rate_limit()
async def post_history(
    request: Request,
    response: Response,
    body: HistoryEntryPayload,
    user: Annotated[UserContext, Depends(require_plan("pro"))],
):
    redis_client = getattr(request.app.state, "redis", None)
    await persist_session_entry(
        redis_client=redis_client,
        supabase_client=getattr(request.app.state, "supabase", None),
        user_id=user.user_id,
        query=body.query,
        language=body.language,
        domain=body.domain,
        response_text=body.response_summary,
        citations=body.citations,
    )
    return {"status": "created"}


@router.delete("/history/{entry_id}", status_code=204, response_model=None)
@apply_query_rate_limit()
async def delete_history_entry(
    request: Request,
    response: Response,
    entry_id: str,
    user: Annotated[UserContext, Depends(require_plan("pro"))],
):
    if not request.app.state.supabase:
        raise HTTPException(503, "History storage unavailable")
    deleted = await delete_session_entry(
        redis_client=getattr(request.app.state, "redis", None),
        supabase_client=request.app.state.supabase,
        user_id=user.user_id,
        entry_id=entry_id,
    )
    if not deleted:
        raise HTTPException(404, "History entry not found")


@router.patch("/history/{entry_id}")
@apply_query_rate_limit()
async def rename_history_entry(
    request: Request,
    response: Response,
    entry_id: str,
    body: HistoryRenamePayload,
    user: Annotated[UserContext, Depends(require_plan("pro"))],
):
    if not request.app.state.supabase:
        raise HTTPException(503, "History storage unavailable")
    renamed = await rename_session_entry(
        redis_client=getattr(request.app.state, "redis", None),
        supabase_client=request.app.state.supabase,
        user_id=user.user_id,
        entry_id=entry_id,
        title=body.title,
    )
    if not renamed:
        raise HTTPException(404, "History entry not found")
    return {"status": "renamed"}


@router.get("/agent-runs", response_model=list[AgentRunEntryResponse])
@apply_query_rate_limit()
async def get_agent_run_history(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
    agent_name: Optional[str] = Query(None, max_length=64),
    limit: int = Query(20, ge=1, le=50),
):
    """Past vertical-agent runs (drafts, checklists, eligibility results) —
    distinct from /history's chat Q&A transcript above. Gated by plain
    auth (any signed-in user), not require_plan("pro") like /history: the
    underlying agents span every plan tier (health-triage and
    retrenchment-navigator are free), so a free-tier user must still be
    able to see their own past free-agent output. The rows themselves are
    real, previously-logged runs — agent_runner.py's _log_run() has been
    writing every start/continue call to `agent_runs` all along; this is
    the first endpoint that reads it back.
    """
    supabase_client = getattr(request.app.state, "supabase", None)
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Agent run history is temporarily unavailable")
    return await fetch_agent_run_history(
        supabase_client=supabase_client,
        user_id=user.user_id,
        agent_name=agent_name,
        limit=limit,
    )
