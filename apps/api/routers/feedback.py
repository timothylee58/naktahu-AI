from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

import structlog

from middleware.rate_limit import apply_query_rate_limit
from routers._request_fields import Domain, Language, normalise_language
from services.auth import UserContext, get_optional_user
from services.feedback import submit_feedback
from services.feedback_attachments import ATTACHMENT_PATH_PATTERN, attachment_belongs_to
from services.feedback_guard import clean_text, enforce_rate, enforce_unique, fingerprint, verify_text

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["feedback"])


class FeedbackPayload(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    query: str = Field(..., min_length=1, max_length=2000)
    response_summary: str = Field(..., min_length=1, max_length=2000)
    citations: list[Any] = Field(default_factory=list, max_length=100)
    domain: Domain = "general"
    language: Language = "en"
    rating: Literal[-1, 1]
    comment: Optional[str] = Field(None, max_length=500)
    attachment_path: Optional[str] = Field(None, max_length=100, pattern=ATTACHMENT_PATH_PATTERN)

    @field_validator("language")
    @classmethod
    def _normalise_language(cls, v: Language) -> Language:
        return normalise_language(v)


@router.post("/feedback", status_code=201)
@apply_query_rate_limit()
async def post_feedback(
    request: Request,
    response: Response,
    body: FeedbackPayload,
    optional_user: Annotated[Optional[UserContext], Depends(get_optional_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Feedback service temporarily unavailable")

    if (body.comment or body.attachment_path) and body.rating != -1:
        raise HTTPException(status_code=422, detail="Details are only accepted with a negative rating")
    if body.attachment_path and not (
        optional_user and attachment_belongs_to(body.attachment_path, optional_user.user_id)
    ):
        raise HTTPException(status_code=422, detail="Invalid attachment")

    actor = optional_user.user_id if optional_user else f"anon:{body.session_id}"
    await enforce_rate(request.app.state.redis, actor, kind="submit")

    # query and comment are client-supplied and negative rows are mined into
    # eval candidates (scripts/mine_feedback_gaps.py reads `query`), so they get
    # the injection scan. response_summary is model output that never feeds the
    # miner; scanning it would reject legitimate reports about odd answers.
    comment = clean_text(body.comment) if body.comment else None
    verdict = verify_text(body.query, comment)
    if verdict.decision != "accept":
        logger.warning("feedback_rejected", actor=actor, reasons=verdict.reasons)
        raise HTTPException(status_code=422, detail="Feedback contains disallowed content")

    await enforce_unique(
        request.app.state.redis,
        fingerprint(actor, body.query, str(body.rating), comment or ""),
    )

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
        comment=comment,
        attachment_path=body.attachment_path,
    )
    return {"status": "recorded"}
