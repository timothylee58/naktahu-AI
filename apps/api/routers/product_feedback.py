"""Product feedback (bugs / feature requests / general) — profile page's
"Give Feedback" card. Login required (this is account-attributable
feedback, not the anonymous-friendly per-answer rating in routers/
feedback.py) — see services/product_feedback.py's docstring for why this
is a separate table/endpoint.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user
from services.product_feedback import create_product_feedback, list_own_product_feedback

router = APIRouter(prefix="/api/v1/product-feedback", tags=["product-feedback"])


class ProductFeedbackRequest(BaseModel):
    category: Literal["bug", "feature_request", "general"]
    title: str = Field(..., min_length=1, max_length=150)
    description: str = Field(..., min_length=1, max_length=2000)
    page_context: Optional[str] = Field(None, max_length=200)


@router.post("", status_code=201)
@apply_query_rate_limit()
async def post_product_feedback(
    request: Request,
    response: Response,
    body: ProductFeedbackRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Feedback service is temporarily unavailable")

    row = await create_product_feedback(
        request.app.state.supabase,
        user_id=user.user_id,
        category=body.category,
        title=body.title.strip(),
        description=body.description.strip(),
        page_context=body.page_context.strip() if body.page_context else None,
    )
    return {
        "id": row.get("id"),
        "category": row.get("category", body.category),
        "title": row.get("title", body.title),
        "status": row.get("status", "new"),
        "created_at": row.get("created_at"),
    }


@router.get("")
@apply_query_rate_limit()
async def get_own_product_feedback(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Feedback service is temporarily unavailable")

    results = await list_own_product_feedback(request.app.state.supabase, user_id=user.user_id)
    return {"results": results}
