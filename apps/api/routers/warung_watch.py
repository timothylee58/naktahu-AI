"""Warung Watch — crowdsourced live "how busy is it right now" check-ins.

Public reads (status/search), rate-limited writes (check-in), optional
auth throughout — mirrors share.py/feedback.py's shape exactly. See
services/warung_watch.py's module docstring for the source model.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_optional_user
from services.warung_watch import (
    create_checkin,
    find_best_warung_match,
    get_or_create_warung,
    get_status,
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
    )
    return {"warung": warung, "checkin": checkin}
