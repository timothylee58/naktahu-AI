"""app/routers/investor.py — Investor Intelligence (investor-plan only).

POST /api/v1/investor/match     thesis-vs-grant match (three result sections)
POST /api/v1/investor/profile   create/update the caller's own saved profile
GET  /api/v1/investor/profile   read the caller's own saved profile

ENTITLEMENT: every endpoint here is gated by require_entitlement("investor"),
a PARALLEL entitlement — not a rung on middleware/plan_gate._PLAN_RANK. A
business-plan customer does NOT inherit investor intelligence and an
investor-plan customer does NOT inherit pro/business SME features; they are
different market segments. Anonymous -> 401 (from get_current_user),
authenticated-but-not-entitled -> 403, matching require_plan's shape.

Mounted in BOTH apps/api/main.py and apps/api/app/main.py per Trap #1.
Supabase-null -> 503 at the top of every endpoint per Trap #4.
"""
from __future__ import annotations

from typing import Annotated, Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.agents.investor_intelligence import VALID_STAGES, investor_match
from middleware.plan_gate import require_entitlement
from middleware.rate_limit import apply_query_rate_limit
from routers._request_fields import Language, normalise_language
from services.auth import UserContext

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/investor", tags=["investor"])

_UNAVAILABLE = "Investor Intelligence is temporarily unavailable"

InvestorUser = Annotated[UserContext, Depends(require_entitlement("investor"))]


# ── Request models (bounded fields per CLAUDE.md hard rule) ──────────────────
class InvestorProfileBody(BaseModel):
    """Inline investment thesis. Shared by /match and /profile."""

    firm_name: Optional[str] = Field(None, min_length=1, max_length=200)
    thesis: Optional[str] = Field(None, min_length=1, max_length=4000)
    stage: list[str] = Field(default_factory=list, max_length=10)
    sectors: list[str] = Field(default_factory=list, max_length=20)
    ticket_size_min_myr: Optional[float] = Field(None, ge=0, le=1e12)
    ticket_size_max_myr: Optional[float] = Field(None, ge=0, le=1e12)
    co_investment_mandate: bool = False

    @field_validator("stage")
    @classmethod
    def _valid_stages(cls, v: list[str]) -> list[str]:
        for s in v:
            if s not in VALID_STAGES:
                raise ValueError(f"stage must be one of {list(VALID_STAGES)}")
        return v

    @field_validator("sectors")
    @classmethod
    def _bounded_sectors(cls, v: list[str]) -> list[str]:
        for s in v:
            if not (1 <= len(s.strip()) <= 64):
                raise ValueError("each sector must be 1-64 characters")
        return v


class MatchRequest(BaseModel):
    """Either `profile` inline, or `profile_id` referencing a saved row.

    Both are supported deliberately: `profile_id` is the normal path for a
    logged-in fund that has saved its thesis once, while the inline `profile`
    lets an investor model a hypothetical thesis ("what if we moved to
    series_a?") without mutating their saved one. Exactly one must be given —
    accepting both would leave it ambiguous which thesis produced the answer.
    """

    profile_id: Optional[str] = Field(None, min_length=1, max_length=64)
    profile: Optional[InvestorProfileBody] = None
    language: Language = "en"

    @field_validator("language")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalise_language(v)


# ── Response models ──────────────────────────────────────────────────────────
class ProgrammeSummary(BaseModel):
    programme_name: str = Field("", max_length=200)
    agency: str = Field("", max_length=200)
    grant_type: str = Field("", max_length=32)
    amount_min_myr: Optional[float] = None
    amount_max_myr: Optional[float] = None
    eligible_sectors: list[str] = Field(default_factory=list, max_length=20)
    application_deadline: Optional[str] = Field(None, max_length=32)
    deadline_is_rolling: bool = False
    budget_year: Optional[int] = None
    application_url: Optional[str] = Field(None, max_length=500)
    source_url: Optional[str] = Field(None, max_length=500)


class StageAlignment(BaseModel):
    programme_name: str = Field("", max_length=200)
    target_stages: list[str] = Field(default_factory=list, max_length=10)
    company_age_min_months: Optional[int] = None
    investor_stages: list[str] = Field(default_factory=list, max_length=10)
    aligned: bool
    mismatch_reason: Optional[str] = Field(None, max_length=1000)
    stage_inference_basis: str = Field("", max_length=500)


class CoInvestmentMandate(ProgrammeSummary):
    co_investment_note: str = Field("", max_length=2000)
    matches_co_investment_mandate: bool = False
    ticket_band_overlaps: bool = True


class Citation(BaseModel):
    title: str = Field("", max_length=300)
    ministry: str = Field("", max_length=200)
    url: str = Field("", max_length=500)
    confidence: float = 0.0


class MatchResponse(BaseModel):
    active_programmes: list[ProgrammeSummary] = Field(default_factory=list, max_length=50)
    stage_alignment: list[StageAlignment] = Field(default_factory=list, max_length=50)
    co_investment_mandates: list[CoInvestmentMandate] = Field(default_factory=list, max_length=50)
    citations: list[Citation] = Field(default_factory=list, max_length=20)
    stage_mismatch_count: int = Field(0, ge=0)
    advice: list[str] = Field(default_factory=list, max_length=10)
    degraded: bool = False
    language: str = Field("en", max_length=8)


class ProfileResponse(BaseModel):
    id: Optional[str] = Field(None, max_length=64)
    firm_name: Optional[str] = Field(None, max_length=200)
    thesis: Optional[str] = Field(None, max_length=4000)
    stage: list[str] = Field(default_factory=list, max_length=10)
    sectors: list[str] = Field(default_factory=list, max_length=20)
    ticket_size_min_myr: Optional[float] = None
    ticket_size_max_myr: Optional[float] = None
    co_investment_mandate: bool = False


def _supabase_or_503(request: Request) -> Any:
    supabase = getattr(request.app.state, "supabase", None)
    if not supabase:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return supabase


def _row_to_profile(row: dict[str, Any]) -> ProfileResponse:
    return ProfileResponse(
        id=str(row.get("id")) if row.get("id") else None,
        firm_name=row.get("firm_name"),
        thesis=row.get("thesis"),
        stage=list(row.get("stage") or [])[:10],
        sectors=list(row.get("sectors") or [])[:20],
        ticket_size_min_myr=row.get("ticket_size_min_myr"),
        ticket_size_max_myr=row.get("ticket_size_max_myr"),
        co_investment_mandate=bool(row.get("co_investment_mandate")),
    )


async def _load_profile(supabase: Any, user_id: str, profile_id: str) -> dict[str, Any]:
    """Owner-scoped fetch. 404s rather than 403s on someone else's id so the
    endpoint never confirms that another fund's profile exists."""
    try:
        res = await (
            supabase.table("investor_profiles")
            .select("*")
            .eq("id", profile_id)
            .eq("user_id", user_id)
            .execute()
        )
        rows = list(res.data or [])
    except Exception as exc:
        log.warning("investor_profile_lookup_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="Investor profile not found")
    return rows[0]


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.post("/match", response_model=MatchResponse)
@apply_query_rate_limit()
async def post_match(
    request: Request,
    response: Response,
    body: MatchRequest,
    user: InvestorUser,
) -> MatchResponse:
    """Match an investment thesis against the live grant catalogue."""
    supabase = _supabase_or_503(request)

    if bool(body.profile_id) == bool(body.profile):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of profile_id or profile.",
        )

    if body.profile_id:
        row = await _load_profile(supabase, user.user_id, body.profile_id)
        profile: dict[str, Any] = {
            "thesis": row.get("thesis"),
            "stage": list(row.get("stage") or []),
            "sectors": list(row.get("sectors") or []),
            "ticket_size_min_myr": row.get("ticket_size_min_myr"),
            "ticket_size_max_myr": row.get("ticket_size_max_myr"),
            "co_investment_mandate": bool(row.get("co_investment_mandate")),
        }
    else:
        assert body.profile is not None  # guaranteed by the XOR check above
        profile = body.profile.model_dump()

    result = await investor_match(profile, supabase, language=body.language)
    log.info(
        "investor_match_completed",
        user_id=user.user_id,
        programmes=len(result["active_programmes"]),
        mismatches=result["stage_mismatch_count"],
        degraded=result["degraded"],
    )
    return MatchResponse(**result)


@router.post("/profile", response_model=ProfileResponse)
@apply_query_rate_limit()
async def upsert_profile(
    request: Request,
    response: Response,
    body: InvestorProfileBody,
    user: InvestorUser,
) -> ProfileResponse:
    """Create or update the caller's own investor profile (one per user)."""
    supabase = _supabase_or_503(request)

    if (
        body.ticket_size_min_myr is not None
        and body.ticket_size_max_myr is not None
        and body.ticket_size_min_myr > body.ticket_size_max_myr
    ):
        raise HTTPException(
            status_code=422, detail="ticket_size_min_myr must not exceed ticket_size_max_myr"
        )

    payload = {**body.model_dump(), "user_id": user.user_id}
    try:
        res = await (
            supabase.table("investor_profiles")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
        rows = list(res.data or [])
    except Exception as exc:
        log.warning("investor_profile_upsert_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from exc

    return _row_to_profile(rows[0] if rows else payload)


@router.get("/profile", response_model=ProfileResponse)
@apply_query_rate_limit()
async def get_profile(
    request: Request,
    response: Response,
    user: InvestorUser,
) -> ProfileResponse:
    """Read the caller's own investor profile."""
    supabase = _supabase_or_503(request)
    try:
        res = await (
            supabase.table("investor_profiles")
            .select("*")
            .eq("user_id", user.user_id)
            .execute()
        )
        rows = list(res.data or [])
    except Exception as exc:
        log.warning("investor_profile_read_failed", error=str(exc))
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from exc

    if not rows:
        raise HTTPException(status_code=404, detail="Investor profile not found")
    return _row_to_profile(rows[0])
