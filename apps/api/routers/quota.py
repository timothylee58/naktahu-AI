"""Read-only view of the caller's free daily query quota, for the homepage
meter. Never increments: enforcement stays in app/routers/query.py, and this
keys the counter exactly the way that router does so the numbers agree.
"""
from __future__ import annotations

from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import anonymous_limiter
from services.auth import UserContext, get_optional_user
from services.daily_quota import FREE_DAILY_LIMIT, get_daily_usage, is_free_plan

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/quota", tags=["quota"])


class DailyQuotaResponse(BaseModel):
    used: int = Field(..., ge=0, le=1_000_000)
    limit: Optional[int] = Field(None, ge=1, le=1_000_000)
    unlimited: bool
    authenticated: bool


@router.get("/daily", response_model=DailyQuotaResponse)
@anonymous_limiter.limit("60/minute")
async def get_daily_quota(
    request: Request,
    response: Response,
    optional_user: Annotated[Optional[UserContext], Depends(get_optional_user)],
) -> DailyQuotaResponse:
    plan = optional_user.plan if optional_user else "free"
    if not is_free_plan(plan):
        return DailyQuotaResponse(used=0, limit=None, unlimited=True, authenticated=True)

    identifier = (
        f"auth:{optional_user.user_id}"
        if optional_user
        else f"anon:{request.client.host if request.client else 'unknown'}"
    )
    try:
        used = await get_daily_usage(getattr(request.app.state, "redis", None), identifier)
    except Exception:
        # A cache outage must not break the homepage; the server still enforces.
        logger.warning("daily_quota_peek_failed")
        used = 0
    return DailyQuotaResponse(
        used=min(used, FREE_DAILY_LIMIT),
        limit=FREE_DAILY_LIMIT,
        unlimited=False,
        authenticated=optional_user is not None,
    )
