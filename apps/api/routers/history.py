from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from services.auth import UserContext, get_current_user
from services.history import fetch_history_entries, persist_session_entry

router = APIRouter(prefix="/api/v1", tags=["history"])


class HistoryEntryPayload(BaseModel):
    query: str
    language: str = "en"
    domain: str = "general"
    response_summary: str = Field(..., max_length=150)
    citations: list[Any] = Field(default_factory=list)


@router.get("/history")
async def get_history(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    redis_client = request.app.state.redis
    entries = await fetch_history_entries(redis_client, user.user_id)
    return entries


@router.post("/history", status_code=201)
async def post_history(
    request: Request,
    body: HistoryEntryPayload,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    redis_client = request.app.state.redis
    await persist_session_entry(
        redis_client=redis_client,
        supabase_client=request.app.state.supabase,
        user_id=user.user_id,
        query=body.query,
        language=body.language,
        domain=body.domain,
        response_text=body.response_summary,
        citations=body.citations,
    )
    return {"status": "created"}
