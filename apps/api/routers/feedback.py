from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_optional_user
from services.feedback import submit_feedback

router = APIRouter(prefix="/api/v1", tags=["feedback"])


class FeedbackPayload(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    query: str = Field(..., min_length=1, max_length=2000)
    response_summary: str = Field(..., min_length=1, max_length=2000)
    citations: list[Any] = Field(default_factory=list)
    domain: str = "general"
    language: str = "en"
    rating: Literal[-1, 1]


@router.post("/feedback", status_code=201)
@apply_query_rate_limit()
async def post_feedback(
    request: Request,
    response: Response,
    body: FeedbackPayload,
    optional_user: Annotated[Optional[UserContext], Depends(get_optional_user)],
):
    await submit_feedback(
        supabase_client=request.app.state.supabase,
        user_id=optional_user.user_id if optional_user else None,
        session_id=body.session_id,
        query=body.query,
        response_text=body.response_summary,
        citations=body.citations,
        domain=body.domain,
        language=body.language,
        rating=body.rating,
    )
    return {"status": "recorded"}
