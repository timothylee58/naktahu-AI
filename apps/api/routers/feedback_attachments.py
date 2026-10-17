"""Screenshot upload for feedback. Verified, re-encoded, and stored privately;
the returned attachment_path is then quoted in a feedback submission.
"""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user
from services.feedback_attachments import store_attachment
from services.feedback_guard import MAX_IMAGE_BYTES, ImageRejected, enforce_rate, verify_image

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/feedback-attachments", tags=["feedback"])


class AttachmentResponse(BaseModel):
    attachment_path: str = Field(..., max_length=100)


@router.post("", status_code=201, response_model=AttachmentResponse)
@apply_query_rate_limit()
async def upload_feedback_attachment(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
    file: Annotated[UploadFile, File(...)],
) -> AttachmentResponse:
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Feedback service is temporarily unavailable")

    await enforce_rate(request.app.state.redis, user.user_id, kind="upload")

    # Read one byte past the cap so oversize is detected without buffering a
    # multi-hundred-MB body.
    data = await file.read(MAX_IMAGE_BYTES + 1)
    try:
        image = verify_image(data)
    except ImageRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    try:
        path = await store_attachment(request.app.state.supabase, user_id=user.user_id, image=image)
    except Exception:
        logger.exception("feedback_attachment_store_failed", user_id=user.user_id)
        raise HTTPException(status_code=503, detail="Attachment storage is temporarily unavailable") from None
    return AttachmentResponse(attachment_path=path)
