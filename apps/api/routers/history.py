from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from middleware.plan_gate import require_plan
from middleware.rate_limit import apply_query_rate_limit
from routers._request_fields import Domain, Language
from services.auth import UserContext
from services.history import fetch_history_entries, persist_session_entry

router = APIRouter(prefix="/api/v1", tags=["history"])


class HistoryEntryPayload(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    language: Language = "en"
    domain: Domain = "general"
    response_summary: str = Field(..., max_length=150)
    citations: list[Any] = Field(default_factory=list, max_length=100)


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
