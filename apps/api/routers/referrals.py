"""Referral program endpoints: fetch/create the caller's share code, and
apply a friend's code (signup + apply IS "completion" — see
services/referral.py's module docstring)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user
from services.referral import apply_referral_code, get_referral_summary

router = APIRouter(prefix="/api/v1/referrals", tags=["referrals"])


class ApplyReferralRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=16)


@router.get("/me")
async def get_my_referral(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Referrals are temporarily unavailable")
    return await get_referral_summary(request.app.state.supabase, user.user_id)


@router.post("/apply")
@apply_query_rate_limit()
async def apply_referral(
    request: Request,
    response: Response,
    body: ApplyReferralRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Referrals are temporarily unavailable")
    result = await apply_referral_code(request.app.state.supabase, body.code, user.user_id)
    if result["status"] == "invalid_code":
        raise HTTPException(status_code=404, detail="Referral code not found")
    if result["status"] == "self_referral_blocked":
        raise HTTPException(status_code=422, detail="You cannot refer yourself")
    return result
