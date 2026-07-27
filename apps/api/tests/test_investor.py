"""tests/test_investor.py — Investor Intelligence layer.

Covers the matcher unit behaviour and the endpoint contract, with the
entitlement boundary as the load-bearing case: `investor` is a PARALLEL
entitlement, so a `business`-plan user must get 403 exactly like a `free`
one. If that test ever starts passing with 200, someone has added `investor`
to _PLAN_RANK and business is silently inheriting a product it did not buy.

Supabase is mocked following tests/test_grant_compatibility.py: a MagicMock
whose terminal .execute() is an AsyncMock (this repo's Supabase client is
awaited — see grant_rag_node).
"""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.investor_intelligence import infer_target_stages, investor_match
from app.routers import investor as investor_router
from core.config import settings

MDAG = "Malaysia Digital Acceleration Grant (MDAG)"
MTDC = "MTDC Sandbox Fund 4"


GRANT_ROWS: list[dict[str, Any]] = [
    {
        "programme_name": "CIP Spark",
        "agency": "Cradle Fund",
        "grant_type": "non_dilutive",
        "amount_min_myr": 50000,
        "amount_max_myr": 150000,
        "eligible_sectors": ["technology", "ai"],
        "company_age_min_months": 0,
        "budget_year": 2026,
        "is_active": True,
        "deadline_is_rolling": False,
        "application_deadline": None,
        "application_url": "https://cradle.com.my/programmes/cip-spark",
        "source_url": "https://cradle.com.my/programmes",
        "notes_en": "Idea-to-prototype stage. Conditional convertible grant.",
    },
    {
        "programme_name": MDAG,
        "agency": "MDEC",
        "grant_type": "matching",
        "amount_min_myr": 100000,
        "amount_max_myr": 500000,
        "eligible_sectors": ["ai", "blockchain"],
        "company_age_min_months": 12,
        "budget_year": 2026,
        "is_active": True,
        "deadline_is_rolling": False,
        "application_deadline": None,
        "application_url": "https://www.mdec.my/malaysia-digital/mdag",
        "source_url": "https://www.mdec.my",
        "notes_en": "RM53M allocation Budget 2026. Requires Malaysia Digital registration.",
    },
    {
        "programme_name": MTDC,
        "agency": "MTDC",
        "grant_type": "conditional",
        "amount_min_myr": 250000,
        "amount_max_myr": 5000000,
        "eligible_sectors": ["technology", "deeptech", "ai"],
        "company_age_min_months": 12,
        "budget_year": 2026,
        "is_active": True,
        "deadline_is_rolling": False,
        "application_deadline": None,
        "application_url": "https://www.mtdc.com.my/products-services-listing/sandbox-fund/",
        "source_url": "https://www.mtdc.com.my",
        "notes_en": "Corporate co-investment model. Requires corporate investor co-commitment.",
    },
    {
        # No URL at all -> must NOT produce a citation (no fabricated URLs).
        "programme_name": "Unsourced Pilot Fund",
        "agency": "Unknown",
        "grant_type": "matching",
        "amount_min_myr": 1000,
        "amount_max_myr": 2000,
        "eligible_sectors": ["ai"],
        "company_age_min_months": 0,
        "budget_year": 2025,
        "is_active": True,
        "application_url": None,
        "source_url": None,
        "notes_en": "",
    },
]

PROFILE = {
    "thesis": "Early-stage Malaysian AI infrastructure",
    "stage": ["pre_seed", "seed"],
    "sectors": ["ai"],
    "ticket_size_min_myr": 250000,
    "ticket_size_max_myr": 2000000,
    "co_investment_mandate": True,
}

PROFILE_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "user_id": "investor-user",
    "firm_name": "Tanjung Ventures",
    **PROFILE,
}


def _mock_supabase(
    *, grants: list[dict[str, Any]] | None = None, profiles: list[dict[str, Any]] | None = None
) -> MagicMock:
    """`grants=None` simulates grant_database being unavailable (migration
    not applied yet, Trap #5)."""
    sb = MagicMock()

    def _table(name: str) -> MagicMock:
        chain = MagicMock()
        if name == "grant_database":
            call = chain.select.return_value.eq.return_value.or_.return_value
            if grants is None:
                call.execute = AsyncMock(
                    side_effect=Exception('relation "grant_database" does not exist')
                )
            else:
                call.execute = AsyncMock(return_value=MagicMock(data=list(grants)))
        else:  # investor_profiles
            rows = list(profiles or [])
            chain.select.return_value.eq.return_value.execute = AsyncMock(
                return_value=MagicMock(data=rows)
            )
            chain.select.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
                return_value=MagicMock(data=rows)
            )
            chain.upsert.return_value.execute = AsyncMock(
                return_value=MagicMock(data=rows or [PROFILE_ROW])
            )
        return chain

    sb.table.side_effect = _table
    return sb


@pytest.fixture(autouse=True)
def _no_network_rag(monkeypatch):
    """The Research Synthesiser fan-out hits RAG; stub it for every test."""
    monkeypatch.setattr(
        "app.agents.investor_intelligence._fetch_context_citations",
        AsyncMock(return_value=[]),
    )


def _headers(plan: str, user_id: str = "u-1", entitlements: list[str] | None = None) -> dict[str, str]:
    app_metadata: dict[str, Any] = {"plan": plan}
    if entitlements is not None:
        app_metadata["entitlements"] = entitlements
    token = jwt.encode(
        {
            "sub": user_id,
            "aud": settings.supabase_jwt_aud,
            "app_metadata": app_metadata,
            "exp": int(time.time()) + 3600,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _client(supabase: Any) -> TestClient:
    app = FastAPI()
    app.include_router(investor_router.router)
    app.state.supabase = supabase
    return TestClient(app)


MATCH_BODY = {"profile": PROFILE, "language": "en"}


# ═══════════════════════════════════════════════════════════════════════════
# MATCHER
# ═══════════════════════════════════════════════════════════════════════════
class TestMatcher:

    @pytest.mark.asyncio
    async def test_three_sections_populated(self):
        result = await investor_match(PROFILE, _mock_supabase(grants=GRANT_ROWS))
        assert {"active_programmes", "stage_alignment", "co_investment_mandates"} <= set(result)
        names = [p["programme_name"] for p in result["active_programmes"]]
        assert "CIP Spark" in names and MDAG in names
        assert result["degraded"] is False

    @pytest.mark.asyncio
    async def test_stage_mismatch_flagged_for_preseed_investor(self):
        result = await investor_match(PROFILE, _mock_supabase(grants=GRANT_ROWS))
        by_name = {s["programme_name"]: s for s in result["stage_alignment"]}
        # 0-month minimum -> pre_seed/seed -> aligned with this investor.
        assert by_name["CIP Spark"]["aligned"] is True
        # 12-month minimum -> seed/series_a; investor is pre_seed+seed, so the
        # sets still intersect at "seed" and this is NOT a mismatch.
        assert by_name[MDAG]["aligned"] is True
        assert result["stage_mismatch_count"] == 0

    @pytest.mark.asyncio
    async def test_pure_preseed_investor_gets_mismatch_reason(self):
        profile = {**PROFILE, "stage": ["pre_seed"]}
        result = await investor_match(profile, _mock_supabase(grants=GRANT_ROWS))
        by_name = {s["programme_name"]: s for s in result["stage_alignment"]}
        entry = by_name[MDAG]
        assert entry["aligned"] is False
        assert "12 months" in entry["mismatch_reason"]
        assert entry["stage_inference_basis"]
        assert result["stage_mismatch_count"] >= 1

    @pytest.mark.asyncio
    async def test_co_investment_mandates_budget_2026_only(self):
        result = await investor_match(PROFILE, _mock_supabase(grants=GRANT_ROWS))
        names = [g["programme_name"] for g in result["co_investment_mandates"]]
        assert MTDC in names
        # 2025 programme excluded even though it is a matching grant.
        assert "Unsourced Pilot Fund" not in names
        mtdc = next(g for g in result["co_investment_mandates"] if g["programme_name"] == MTDC)
        assert "co-investment" in mtdc["co_investment_note"].lower()
        assert mtdc["matches_co_investment_mandate"] is True

    @pytest.mark.asyncio
    async def test_no_citation_without_a_real_url(self):
        result = await investor_match(PROFILE, _mock_supabase(grants=GRANT_ROWS))
        urls = [c["url"] for c in result["citations"]]
        assert all(u.startswith("http") for u in urls)
        assert all("Unsourced Pilot Fund" != c["title"] for c in result["citations"])

    def test_stage_inference_bands(self):
        assert infer_target_stages({"company_age_min_months": 0}) == ("pre_seed", "seed")
        assert infer_target_stages({"company_age_min_months": 12}) == ("seed", "series_a")
        assert "series_b" in infer_target_stages({"company_age_min_months": 36})

    @pytest.mark.asyncio
    async def test_grant_database_missing_degrades(self):
        result = await investor_match(PROFILE, _mock_supabase(grants=None))
        assert result["degraded"] is True
        assert result["active_programmes"] == []
        assert result["advice"]

    @pytest.mark.asyncio
    async def test_supabase_none_does_not_crash(self):
        result = await investor_match(PROFILE, None)
        assert result["degraded"] is True
        assert result["active_programmes"] == []


# ═══════════════════════════════════════════════════════════════════════════
# ENTITLEMENT BOUNDARY — the load-bearing tests
# ═══════════════════════════════════════════════════════════════════════════
class TestEntitlementBoundary:

    def test_anonymous_401(self):
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json=MATCH_BODY
        )
        assert res.status_code == 401

    def test_free_plan_403(self):
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json=MATCH_BODY, headers=_headers("free")
        )
        assert res.status_code == 403

    def test_business_plan_403_not_a_ladder_rung(self):
        """business is the TOP of _PLAN_RANK and must still be refused."""
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json=MATCH_BODY, headers=_headers("business")
        )
        assert res.status_code == 403

    def test_pro_plan_403(self):
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json=MATCH_BODY, headers=_headers("pro")
        )
        assert res.status_code == 403

    def test_investor_plan_200(self):
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json=MATCH_BODY, headers=_headers("investor")
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["active_programmes"] and body["stage_alignment"]
        assert body["co_investment_mandates"]

    def test_entitlements_list_grants_access_without_investor_plan(self):
        """A pro-plan fund can hold the investor entitlement explicitly."""
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match",
            json=MATCH_BODY,
            headers=_headers("pro", entitlements=["investor"]),
        )
        assert res.status_code == 200, res.text

    def test_investor_plan_does_not_inherit_business_rank(self):
        """The parallel entitlement must not leak back into the plan ladder."""
        from middleware.plan_gate import _PLAN_RANK

        assert "investor" not in _PLAN_RANK


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT CONTRACT
# ═══════════════════════════════════════════════════════════════════════════
class TestMatchEndpoint:

    def test_profile_id_path_loads_saved_row(self):
        sb = _mock_supabase(grants=GRANT_ROWS, profiles=[PROFILE_ROW])
        res = _client(sb).post(
            "/api/v1/investor/match",
            json={"profile_id": PROFILE_ROW["id"]},
            headers=_headers("investor"),
        )
        assert res.status_code == 200, res.text
        assert res.json()["active_programmes"]

    def test_profile_id_not_found_404(self):
        sb = _mock_supabase(grants=GRANT_ROWS, profiles=[])
        res = _client(sb).post(
            "/api/v1/investor/match",
            json={"profile_id": PROFILE_ROW["id"]},
            headers=_headers("investor"),
        )
        assert res.status_code == 404

    def test_both_profile_and_profile_id_422(self):
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match",
            json={"profile_id": PROFILE_ROW["id"], "profile": PROFILE},
            headers=_headers("investor"),
        )
        assert res.status_code == 422

    def test_neither_profile_nor_profile_id_422(self):
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json={}, headers=_headers("investor")
        )
        assert res.status_code == 422

    def test_invalid_stage_422(self):
        body = {"profile": {**PROFILE, "stage": ["series_z"]}}
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json=body, headers=_headers("investor")
        )
        assert res.status_code == 422

    def test_oversized_thesis_422(self):
        body = {"profile": {**PROFILE, "thesis": "x" * 4001}}
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json=body, headers=_headers("investor")
        )
        assert res.status_code == 422

    def test_too_many_sectors_422(self):
        body = {"profile": {**PROFILE, "sectors": [f"s{i}" for i in range(21)]}}
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match", json=body, headers=_headers("investor")
        )
        assert res.status_code == 422

    def test_bad_language_422(self):
        res = _client(_mock_supabase(grants=GRANT_ROWS)).post(
            "/api/v1/investor/match",
            json={"profile": PROFILE, "language": "fr"},
            headers=_headers("investor"),
        )
        assert res.status_code == 422

    def test_supabase_none_503(self):
        res = _client(None).post(
            "/api/v1/investor/match", json=MATCH_BODY, headers=_headers("investor")
        )
        assert res.status_code == 503

    def test_grant_database_missing_returns_200_degraded(self):
        res = _client(_mock_supabase(grants=None)).post(
            "/api/v1/investor/match", json=MATCH_BODY, headers=_headers("investor")
        )
        assert res.status_code == 200, res.text
        assert res.json()["degraded"] is True


class TestProfileEndpoints:

    def test_upsert_and_read(self):
        sb = _mock_supabase(grants=GRANT_ROWS, profiles=[PROFILE_ROW])
        client = _client(sb)
        res = client.post(
            "/api/v1/investor/profile",
            json={"firm_name": "Tanjung Ventures", **PROFILE},
            headers=_headers("investor", user_id="investor-user"),
        )
        assert res.status_code == 200, res.text
        assert res.json()["firm_name"] == "Tanjung Ventures"

        res = client.get(
            "/api/v1/investor/profile",
            headers=_headers("investor", user_id="investor-user"),
        )
        assert res.status_code == 200, res.text
        assert res.json()["sectors"] == ["ai"]

    def test_profile_requires_entitlement(self):
        sb = _mock_supabase(grants=GRANT_ROWS, profiles=[PROFILE_ROW])
        res = _client(sb).get("/api/v1/investor/profile", headers=_headers("business"))
        assert res.status_code == 403

    def test_profile_anonymous_401(self):
        sb = _mock_supabase(grants=GRANT_ROWS, profiles=[PROFILE_ROW])
        assert _client(sb).get("/api/v1/investor/profile").status_code == 401

    def test_inverted_ticket_band_422(self):
        sb = _mock_supabase(grants=GRANT_ROWS, profiles=[PROFILE_ROW])
        res = _client(sb).post(
            "/api/v1/investor/profile",
            json={"ticket_size_min_myr": 5000000, "ticket_size_max_myr": 1000},
            headers=_headers("investor"),
        )
        assert res.status_code == 422

    def test_profile_missing_404(self):
        sb = _mock_supabase(grants=GRANT_ROWS, profiles=[])
        res = _client(sb).get("/api/v1/investor/profile", headers=_headers("investor"))
        assert res.status_code == 404

    def test_profile_supabase_none_503(self):
        res = _client(None).get("/api/v1/investor/profile", headers=_headers("investor"))
        assert res.status_code == 503
