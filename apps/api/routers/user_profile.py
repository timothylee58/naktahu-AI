"""routers/user_profile.py — the caller's saved "about you" profile.

GET    /api/v1/me/profile   read it (all fields null if nothing saved yet)
PUT    /api/v1/me/profile   replace it with exactly what is sent
DELETE /api/v1/me/profile   delete it

Open to every signed-in user (Free and Pro): the profile only removes retyping,
it unlocks nothing. Every field is optional and self-declared; nothing here is
inferred, and `is_bumiputera` is opt-in (null = not shared).

The API uses the service-role Supabase client (RLS bypassed), so every query is
filtered on the caller's own user_id. Mounted in main.py, the single app.
Needs migration 063; until it is applied the endpoints answer 503, not crash.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.agents.runtime import execute_query
from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/me", tags=["profile"])

_UNAVAILABLE = "Your profile is temporarily unavailable"

State = Literal[
    "johor", "kedah", "kelantan", "melaka", "negeri_sembilan", "pahang", "penang", "perak",
    "perlis", "sabah", "sarawak", "selangor", "terengganu", "kl", "labuan", "putrajaya",
]
EmploymentStatus = Literal["employed", "self_employed", "unemployed", "retired", "student"]
BusinessType = Literal["sole_prop", "sdn_bhd", "startup", "llp", "cooperative"]
Sector = Literal[
    "technology", "ai", "fintech", "edtech", "healthtech", "digital", "deeptech", "biotech",
    "manufacturing", "agriculture", "services",
]

_FIELDS = (
    "state", "postcode", "employment_status", "business_type", "sector",
    "household_size", "is_bumiputera",
)


class ProfileBody(BaseModel):
    """What the user chose to share. Omitted or null = not shared."""

    state: Optional[State] = None
    postcode: Optional[str] = Field(None, pattern=r"^\d{5}$")
    employment_status: Optional[EmploymentStatus] = None
    business_type: Optional[BusinessType] = None
    sector: Optional[Sector] = None
    household_size: Optional[int] = Field(None, ge=1, le=30)
    is_bumiputera: Optional[bool] = None


class ProfileResponse(ProfileBody):
    updated_at: Optional[str] = None


def _supabase_or_503(request: Request) -> Any:
    supabase = getattr(request.app.state, "supabase", None)
    if not supabase:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return supabase


def _row_to_response(row: dict[str, Any] | None) -> ProfileResponse:
    row = row or {}
    data: dict[str, Any] = {f: row.get(f) for f in _FIELDS}
    data["updated_at"] = row.get("updated_at")
    return ProfileResponse(**data)


@router.get("/profile", response_model=ProfileResponse)
@apply_query_rate_limit()
async def get_profile(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> ProfileResponse:
    supabase = _supabase_or_503(request)
    try:
        res = await execute_query(
            supabase.table("user_profiles").select("*").eq("user_id", user.user_id).limit(1)
        )
    except Exception as exc:  # noqa: BLE001 — table missing until migration 063 is applied
        log.warning("user_profile_read_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    rows = getattr(res, "data", None) or []
    return _row_to_response(rows[0] if rows else None)


@router.put("/profile", response_model=ProfileResponse)
@apply_query_rate_limit()
async def put_profile(
    request: Request,
    response: Response,
    body: ProfileBody,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> ProfileResponse:
    supabase = _supabase_or_503(request)
    payload: dict[str, Any] = {f: getattr(body, f) for f in _FIELDS}
    payload["user_id"] = user.user_id
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        res = await execute_query(
            supabase.table("user_profiles").upsert(payload, on_conflict="user_id")
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("user_profile_write_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    rows = getattr(res, "data", None) or []
    log.info("user_profile_saved", user_id=user.user_id)  # ids only, never field values
    return _row_to_response(rows[0] if rows else payload)


@router.delete("/profile", status_code=204, response_model=None)
@apply_query_rate_limit()
async def delete_profile(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    supabase = _supabase_or_503(request)
    try:
        await execute_query(
            supabase.table("user_profiles").delete().eq("user_id", user.user_id)
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("user_profile_delete_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    log.info("user_profile_deleted", user_id=user.user_id)
