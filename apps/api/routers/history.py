from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from middleware.plan_gate import require_plan
from middleware.rate_limit import apply_query_rate_limit
from routers._request_fields import Domain, Language, normalise_language
from services.auth import UserContext
from services.history import (
    delete_session_entry,
    fetch_history_entries,
    persist_session_entry,
    rename_session_entry,
)

router = APIRouter(prefix="/api/v1", tags=["history"])


class HistoryRenamePayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)


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
