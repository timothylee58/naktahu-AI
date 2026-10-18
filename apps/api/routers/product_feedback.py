"""Product feedback (bugs / feature requests / general) — profile page's
"Give Feedback" card. Login required (this is account-attributable
feedback, not the anonymous-friendly per-answer rating in routers/
feedback.py) — see services/product_feedback.py's docstring for why this
is a separate table/endpoint.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user
from services.feedback_attachments import ATTACHMENT_PATH_PATTERN, attachment_belongs_to
from services.feedback_guard import clean_text, enforce_rate, enforce_unique, fingerprint, verify_text
from services.product_feedback import create_product_feedback, list_own_product_feedback

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/product-feedback", tags=["product-feedback"])


class ProductFeedbackRequest(BaseModel):
    category: Literal["bug", "feature_request", "general"]
    title: str = Field(..., min_length=1, max_length=150)
    description: str = Field(..., min_length=1, max_length=2000)
    page_context: Optional[str] = Field(None, max_length=200)
    attachment_path: Optional[str] = Field(None, max_length=100, pattern=ATTACHMENT_PATH_PATTERN)


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

    redis = request.app.state.redis
    await enforce_rate(redis, user.user_id, kind="submit")

    title = clean_text(body.title)
    description = clean_text(body.description)
    page_context = clean_text(body.page_context) if body.page_context else None
    if not title or not description:
        raise HTTPException(status_code=422, detail="Feedback cannot be empty")

    verdict = verify_text(title, description, page_context)
    if verdict.decision == "reject":
        logger.warning("product_feedback_rejected", user_id=user.user_id, reasons=verdict.reasons)
        raise HTTPException(status_code=422, detail="Feedback contains disallowed content")
    if body.attachment_path and not attachment_belongs_to(body.attachment_path, user.user_id):
        raise HTTPException(status_code=422, detail="Invalid attachment")

    await enforce_unique(redis, fingerprint(body.category, title, description))

    flagged = verdict.decision == "flag"
    if flagged:
        logger.warning("product_feedback_flagged", user_id=user.user_id, reasons=verdict.reasons)
    try:
        row = await create_product_feedback(
            request.app.state.supabase,
            user_id=user.user_id,
            category=body.category,
            title=title,
            description=description,
            page_context=page_context,
            attachment_path=body.attachment_path,
            status="flagged" if flagged else None,
        )
    except Exception:
        # Pre-migration-058 the 'flagged' status / attachment_path column don't
        # exist; degrade to 503 rather than crash.
        if not (flagged or body.attachment_path):
            raise
        logger.exception("product_feedback_insert_failed", user_id=user.user_id)
        raise HTTPException(status_code=503, detail="Feedback service is temporarily unavailable") from None
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
