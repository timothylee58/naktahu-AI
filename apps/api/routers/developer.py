"""Developer API key management — JWT-authenticated."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from middleware.plan_gate import _PLAN_RANK
from services.api_key_service import (
    VALID_API_PLANS,
    create_api_key_record,
    fetch_usage_stats,
    list_api_keys,
    revoke_api_key,
)
from services.auth import UserContext, get_current_user

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/developer", tags=["developer"])

# Freemium model: the "free" API plan (modest quota, no SSE/multi/widget) is
# open to any signed-in app user regardless of subscription tier. The paid
# API plans (starter/growth/enterprise/widget/white_label — separate from,
# and priced on top of, the app's own free/student/pro/business ladder)
# require at least a Pro app subscription — same bar as history and other
# Pro-gated features (middleware/plan_gate._PLAN_RANK).
PAID_API_PLANS = frozenset(VALID_API_PLANS - {"free"})
MIN_APP_PLAN_FOR_PAID_API_PLANS = "pro"


class CreateKeyRequest(BaseModel):
    plan: Literal["free", "starter", "growth", "enterprise", "widget", "white_label"] = "free"
    domain_whitelist: list[str] = Field(default_factory=list, max_length=10)


class CreateKeyResponse(BaseModel):
    raw_key: str
    key: dict[str, Any]


class KeyListItem(BaseModel):
    id: str
    key_prefix: str
    plan: str
    calls_used: int
    calls_limit: int
    rate_limit_per_min: int
    domain_whitelist: list[str]
    active: bool
    last_used_at: Optional[str] = None
    created_at: Optional[str] = None


class KeyListResponse(BaseModel):
    keys: list[KeyListItem]


class UsageResponse(BaseModel):
    by_domain: dict[str, int]
    by_endpoint: dict[str, int]
    daily: dict[str, int]
    total_events: int


@router.post("/keys", response_model=CreateKeyResponse, status_code=201)
async def create_key(
    body: CreateKeyRequest,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> CreateKeyResponse:
    if body.plan not in VALID_API_PLANS:
        raise HTTPException(status_code=422, detail=f"Invalid plan: {body.plan}")

    if (
        body.plan in PAID_API_PLANS
        and _PLAN_RANK.get(user.plan, 0) < _PLAN_RANK.get(MIN_APP_PLAN_FOR_PAID_API_PLANS, 0)
    ):
        raise HTTPException(
            status_code=403,
            detail="Paid Developer API plans require a Pro subscription or higher.",
        )

    supabase = getattr(request.app.state, "supabase", None)
    if supabase is None:
        raise HTTPException(status_code=503, detail="Key service temporarily unavailable")

    try:
        raw_key, public_row = await create_api_key_record(
            supabase,
            user_id=user.user_id,
            plan=body.plan,
            domain_whitelist=body.domain_whitelist,
        )
    except ValueError as exc:
        if str(exc) == "max_keys_reached":
            raise HTTPException(status_code=400, detail="Maximum of 3 active API keys per account") from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CreateKeyResponse(raw_key=raw_key, key=public_row)


@router.get("/keys", response_model=KeyListResponse)
async def get_keys(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> KeyListResponse:
    supabase = getattr(request.app.state, "supabase", None)
    if supabase is None:
        raise HTTPException(status_code=503, detail="Key service temporarily unavailable")

    rows = await list_api_keys(supabase, user.user_id)
    keys = [
        KeyListItem(
            id=str(r["id"]),
            key_prefix=str(r.get("key_prefix") or ""),
            plan=str(r.get("plan") or "starter"),
            calls_used=int(r.get("calls_used") or 0),
            calls_limit=int(r.get("calls_limit") or 0),
            rate_limit_per_min=int(r.get("rate_limit_per_min") or 10),
            domain_whitelist=list(r.get("domain_whitelist") or []),
            active=bool(r.get("active", True)),
            last_used_at=r.get("last_used_at"),
            created_at=r.get("created_at"),
        )
        for r in rows
    ]
    return KeyListResponse(keys=keys)


@router.delete("/keys/{key_id}", status_code=204, response_model=None)
async def delete_key(
    key_id: str,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> None:
    supabase = getattr(request.app.state, "supabase", None)
    if supabase is None:
        raise HTTPException(status_code=503, detail="Key service temporarily unavailable")

    revoked = await revoke_api_key(supabase, user.user_id, key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> UsageResponse:
    supabase = getattr(request.app.state, "supabase", None)
    if supabase is None:
        raise HTTPException(status_code=503, detail="Usage service temporarily unavailable")

    stats = await fetch_usage_stats(supabase, user.user_id)
    return UsageResponse(**stats)
