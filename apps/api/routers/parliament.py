"""Parliament Watch — read-only structured lookups.

Plain FastAPI router, not a LangGraph agent: every endpoint here is a
direct structured read (MP-by-constituency, full-text search, bill vote
summary, constituency listing) with no multi-turn intake, no generation
step, and no credit cost — the shape that compliance_drafter/
grant_draft_generator exist for (HITL + expensive generation requiring
confirmation before billing) doesn't apply. This is public government
reference data (RLS makes every table public-read), so no auth tier is
required, matching the lightest-gated precedent in routers/share.py
(GET /api/v1/share/{id} takes no auth dependency at all).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from middleware.rate_limit import anonymous_limiter
from services.parliament import (
    get_bill_vote_summary,
    get_mp_by_constituency,
    list_constituencies,
    search_mps,
)

router = APIRouter(prefix="/api/v1/parliament", tags=["parliament"])

_CONSTITUENCY_CODE_RE = re.compile(r"^[A-Za-z]\.?\d{1,3}$")
_BILL_NUMBER_RE = re.compile(r"^[A-Za-z0-9 ./-]{1,64}$")


class MpVoteSummaryEntry(BaseModel):
    vote: str
    vote_count: int
    party_breakdown: Optional[dict[str, Any]] = None


class ConstituencyOut(BaseModel):
    code: str
    name: str
    name_bm: Optional[str] = None
    type: Optional[str] = None
    state: Optional[str] = None
    region: Optional[str] = None
    registered_voters: Optional[int] = None
    last_election: Optional[str] = None


@router.get("/mp/search")
@anonymous_limiter.limit("60/minute")
async def search_mp(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(20, ge=1, le=50),
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Parliament Watch is temporarily unavailable")

    results = await search_mps(request.app.state.supabase, q, limit=limit)
    return {"results": results}


@router.get("/mp/{constituency_code}")
@anonymous_limiter.limit("60/minute")
async def get_mp(request: Request, response: Response, constituency_code: str):
    if not _CONSTITUENCY_CODE_RE.match(constituency_code):
        raise HTTPException(status_code=404, detail="MP not found for this constituency")
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Parliament Watch is temporarily unavailable")

    mp = await get_mp_by_constituency(request.app.state.supabase, constituency_code)
    if not mp:
        raise HTTPException(status_code=404, detail="MP not found for this constituency")
    return mp


@router.get("/bills/{bill_number}/votes")
@anonymous_limiter.limit("60/minute")
async def bill_votes(request: Request, response: Response, bill_number: str):
    if not _BILL_NUMBER_RE.match(bill_number):
        raise HTTPException(status_code=404, detail="Bill not found")
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Parliament Watch is temporarily unavailable")

    summary = await get_bill_vote_summary(request.app.state.supabase, bill_number)
    if not summary:
        raise HTTPException(status_code=404, detail="No vote records found for this bill")
    return {"bill_number": bill_number, "summary": summary}


@router.get("/constituencies")
@anonymous_limiter.limit("60/minute")
async def constituencies(
    request: Request,
    response: Response,
    state: Optional[str] = Query(None, min_length=1, max_length=64),
    limit: int = Query(100, ge=1, le=300),
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Parliament Watch is temporarily unavailable")

    results = await list_constituencies(request.app.state.supabase, state=state, limit=limit)
    return {"results": results}
