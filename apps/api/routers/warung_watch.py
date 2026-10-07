"""Warung Watch — crowdsourced live "how busy is it right now" check-ins.

Public reads (status/search), rate-limited writes (check-in), optional
auth throughout — mirrors share.py/feedback.py's shape exactly. See
services/warung_watch.py's module docstring for the source model.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, model_validator

from middleware.rate_limit import anonymous_limiter, apply_query_rate_limit
from services.auth import UserContext, get_optional_user
from services.warung_watch import (
    create_checkin,
    find_best_warung_match,
    get_or_create_warung,
    get_price_history,
    get_status,
    search_nearby_places,
    search_warungs,
)

router = APIRouter(prefix="/api/v1/warung-watch", tags=["warung-watch"])


class CheckinRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    status: Literal["empty", "moderate", "packed"]
    location: Optional[str] = Field(None, max_length=300)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)
    # Mirrors the ANON_SESSION_KEY localStorage UUID AuthButton.tsx already
    # generates for every visitor — lets an anonymous check-in be traced
    # back to one browser for basic abuse patterns without requiring
    # sign-in for something as low-stakes as "this place looks packed."
    anon_session_id: Optional[str] = Field(None, max_length=64)
    # Optional price report (033_warung_checkin_price.sql) — both fields
    # must be set together, matching the DB's warung_checkins_price_pair_chk
    # constraint; validated again below since Pydantic field-level
    # constraints can't express a cross-field pair rule.
    price_item: Optional[str] = Field(None, min_length=1, max_length=80)
    price_myr: Optional[float] = Field(None, ge=0, le=9999.99)

    @model_validator(mode="after")
    def _price_pair_complete(self) -> "CheckinRequest":
        if (self.price_item is None) != (self.price_myr is None):
            raise ValueError("price_item and price_myr must both be set or both omitted")
        return self


@router.get("/search")
async def warung_search(
    request: Request,
    q: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Warung Watch is temporarily unavailable")
    bounded_limit = max(1, min(limit, 25))
    return await search_warungs(supabase_client=request.app.state.supabase, query=q, limit=bounded_limit)


@router.get("/status")
async def warung_status(request: Request, name: str) -> dict[str, Any]:
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Warung Watch is temporarily unavailable")
    sb = request.app.state.supabase
    warung = await find_best_warung_match(supabase_client=sb, query=name)
    if not warung:
        return {"warung": None, "status": None, "is_fresh": False, "report_count": 0, "last_updated": None, "sources": []}
    status = await get_status(supabase_client=sb, warung_id=warung["id"])
    return {"warung": warung, **status}


@router.get("/nearby")
@anonymous_limiter.limit("20/minute")
async def warung_nearby(
    request: Request,
    response: Response,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(1500, ge=100, le=5000),
) -> dict[str, Any]:
    """Real nearby-place search assist via the official Places API (New) —
    see services/warung_watch.py's module docstring for why this is a
    legitimate integration and Google "Popular Times" is not. Rate-limited
    (not the shared apply_query_rate_limit — a tighter, GET-specific limit)
    since every call costs real Google API quota/billing once
    GOOGLE_PLACES_API_KEY is configured. Never 503s: returns
    {"configured": false, "places": []} when the key isn't set, so the
    frontend can degrade to its Maps-link-only fallback instead of erroring.
    """
    return await search_nearby_places(lat=lat, lng=lng, radius_m=radius_m)


@router.post("/checkin", status_code=201)
@apply_query_rate_limit()
async def warung_checkin(
    request: Request,
    response: Response,
    body: CheckinRequest,
    optional_user: Annotated[Optional[UserContext], Depends(get_optional_user)],
) -> dict[str, Any]:
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Warung Watch is temporarily unavailable")
    sb = request.app.state.supabase

    warung = await get_or_create_warung(
        supabase_client=sb,
        name=body.name,
        location=body.location,
        lat=body.lat,
        lng=body.lng,
        created_by=optional_user.user_id if optional_user else None,
    )
    checkin = await create_checkin(
        supabase_client=sb,
        warung_id=warung["id"],
        status=body.status,
        reporter_id=optional_user.user_id if optional_user else None,
        anon_session_id=body.anon_session_id,
        price_item=body.price_item,
        price_myr=body.price_myr,
    )
    return {"warung": warung, "checkin": checkin}


@router.get("/price-history")
async def warung_price_history(request: Request, name: str, limit: int = 30) -> dict[str, Any]:
    """Real, crowdsourced price-report history for a warung — the data
    source behind the price-trend chart. No fabricated sample points:
    an unmatched or never-priced warung returns an empty list rather than
    a synthetic series, and the frontend renders an honest "not enough
    reports yet" state instead of a chart with faked data (see
    033_warung_checkin_price.sql's module comment)."""
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Warung Watch is temporarily unavailable")
    sb = request.app.state.supabase
    warung = await find_best_warung_match(supabase_client=sb, query=name)
    if not warung:
        return {"warung": None, "history": []}
    bounded_limit = max(1, min(limit, 100))
    history = await get_price_history(supabase_client=sb, warung_id=warung["id"], limit=bounded_limit)
    return {"warung": warung, "history": history}
