import re
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import anonymous_limiter, apply_query_rate_limit
from services.auth import UserContext, get_optional_user
from services.share import create_shared_answer, get_shared_answer

router = APIRouter(prefix="/api/v1/share", tags=["share"])

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


class ShareRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    response_text: str = Field(..., min_length=1, max_length=20000)
    citations: list[Any] = Field(default_factory=list)
    domain: str = "general"
    language: str = "en"
    confidence: Optional[float] = None


@router.post("", status_code=201)
@apply_query_rate_limit()
async def post_share(
    request: Request,
    response: Response,
    body: ShareRequest,
    optional_user: Annotated[Optional[UserContext], Depends(get_optional_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Sharing is temporarily unavailable")

    share_id = await create_shared_answer(
        supabase_client=request.app.state.supabase,
        user_id=optional_user.user_id if optional_user else None,
        query=body.query,
        response_text=body.response_text,
        citations=body.citations,
        domain=body.domain,
        language=body.language,
        confidence=body.confidence,
    )
    return {"id": share_id}


@router.get("/{share_id}")
@anonymous_limiter.limit("60/minute")
async def get_share(request: Request, response: Response, share_id: str):
    if not _UUID_RE.match(share_id):
        raise HTTPException(status_code=404, detail="Shared answer not found")
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Sharing is temporarily unavailable")

    answer = await get_shared_answer(request.app.state.supabase, share_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Shared answer not found")
    return answer
