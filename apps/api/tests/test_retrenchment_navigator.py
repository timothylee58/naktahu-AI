"""Tests for the Retrenchment Navigator agent — nodes, deterministic
statutory-benefit math, graph wiring, and router dispatch."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.checkpointer import reset_checkpointer_for_tests
from core.config import settings
from app.agents.retrenchment_navigator.graph import build_retrenchment_navigator_graph
from app.agents.retrenchment_navigator.nodes import (
    calculate_notice_period_weeks,
    calculate_statutory_benefits,
    intake_node,
    output_node,
    retrenchment_rag_node,
    route_after_intake,
)
from services.agent_registry import load_agent_registry


@pytest.fixture(autouse=True)
def _reset_cp():
    reset_checkpointer_for_tests()
    yield
    reset_checkpointer_for_tests()


# ── Deterministic statutory-benefit calculation ────────────────────────────
# Employment Act 1955, Second Schedule bands: <2y -> 10 days/year,
# 2-5y -> 15 days/year, >=5y -> 20 days/year. Daily wage = monthly / 26.

@pytest.mark.parametrize(
    "years,salary,expected_days_per_year,expected_total_days,expected_benefit",
    [
        (1.0, 2600.0, 10, 10, 1000.0),      # <2y band, daily wage exactly 100
        (1.9, 2600.0, 10, 19, 1900.0),      # still <2y band
        (2.0, 2600.0, 15, 30, 3000.0),      # exactly 2y -> 2-5y band
        (4.9, 2600.0, 15, 74, 7400.0),      # still 2-5y band
        (5.0, 2600.0, 20, 100, 10000.0),    # exactly 5y -> >=5y band
        (10.0, 5200.0, 20, 200, 40000.0),   # long service, higher salary
    ],
)
def test_calculate_statutory_benefits_bands(
    years, salary, expected_days_per_year, expected_total_days, expected_benefit
):
    result = calculate_statutory_benefits(years, salary)
    assert result["days_per_year_of_service"] == expected_days_per_year
    assert result["total_days_owed"] == expected_total_days
    assert result["estimated_benefit_myr"] == pytest.approx(expected_benefit, abs=0.01)
    assert "Employment Act 1955" in result["basis"]


@pytest.mark.parametrize(
    "years,expected_weeks",
    [
        (0.5, 4),
        (1.9, 4),
        (2.0, 6),
        (4.9, 6),
        (5.0, 8),
        (15.0, 8),
    ],
)
def test_calculate_notice_period_weeks_bands(years, expected_weeks):
    assert calculate_notice_period_weeks(years) == expected_weeks


# ── intake_node ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intake_node_extracts_fields_from_message():
    state = {
        "message": "I worked there for 3 years, salary was RM4,500, they gave me 30 days notice, "
        "and yes I was an EIS contributor.",
        "messages": [],
        "turns_count": 0,
    }
    result = await intake_node(state)
    assert result["years_of_service"] == 3.0
    assert result["monthly_salary_myr"] == 4500.0
    assert result["notice_given_days"] == 30.0
    assert result["is_eis_contributor"] is True
    assert result["intake_complete"] is True
    assert result["status"] == "intake_done"


@pytest.mark.asyncio
async def test_intake_node_asks_for_missing_field():
    state = {"message": "I worked there for 3 years.", "messages": [], "turns_count": 0}
    result = await intake_node(state)
    assert result["intake_complete"] is False
    assert result["status"] == "needs_input"
    assert result["next_prompt"] is not None


@pytest.mark.asyncio
async def test_intake_node_completes_after_max_turns_even_if_incomplete():
    state = {"message": "not much info here", "messages": [], "turns_count": 5}
    result = await intake_node(state)
    assert result["turns_count"] == 6
    assert result["intake_complete"] is True


def test_route_after_intake():
    assert route_after_intake({"intake_complete": True}) == "retrenchment_rag"
    assert route_after_intake({"intake_complete": False}) == "__end__"
    assert route_after_intake({}) == "__end__"


# ── retrenchment_rag_node ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrenchment_rag_node_queries_both_domains_and_dedupes():
    legal_findings = [{"source_url": "https://jtksm.mohr.gov.my/a", "summary": "legal finding"}]
    epf_findings = [
        {"source_url": "https://jtksm.mohr.gov.my/a", "summary": "duplicate url"},  # should be deduped
        {"source_url": "https://perkeso.gov.my/b", "summary": "epf finding"},
    ]

    async def fake_query(query, domain, language="bm"):
        return legal_findings if domain == "legal" else epf_findings

    with patch("app.agents.retrenchment_navigator.nodes.query_rag_findings", side_effect=fake_query):
        result = await retrenchment_rag_node({"language": "en", "years_of_service": 3.0, "tool_calls": []})

    assert len(result["_rag_findings"]) == 2
    urls = {f["source_url"] for f in result["_rag_findings"]}
    assert urls == {"https://jtksm.mohr.gov.my/a", "https://perkeso.gov.my/b"}
    assert len(result["tool_calls"]) == 2
    assert {tc["domain"] for tc in result["tool_calls"]} == {"legal", "epf"}


# ── output_node ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_output_node_uses_deterministic_benefits_not_llm():
    """The LLM is only allowed to draft checklist/warnings prose — it must
    never override the computed statutory_benefits/eis_eligibility numbers,
    even if it tries to (simulated here via a JSON payload that includes
    bogus benefit fields the code must simply ignore)."""
    state = {
        "years_of_service": 3.0,
        "monthly_salary_myr": 5200.0,
        "notice_given_days": 10,
        "is_eis_contributor": True,
        "language": "en",
        "_rag_findings": [
            {"source_url": "https://jtksm.mohr.gov.my/a", "source_title": "Termination rights", "summary": "s", "similarity": 0.8}
        ],
    }
    fake_llm_response = (
        '{"checklist": ["Custom step"], "warnings": ["Custom warning"], '
        '"estimated_benefit_myr": 999999.99}'  # must be ignored — not a real output field the code reads
    )
    with patch("app.agents.retrenchment_navigator.nodes.llm_complete", AsyncMock(return_value=fake_llm_response)):
        result = await output_node(state)

    # Deterministic calculation must win regardless of what the LLM returned.
    assert result["statutory_benefits"]["days_per_year_of_service"] == 15
    assert result["statutory_benefits"]["total_days_owed"] == 45
    assert result["statutory_benefits"]["estimated_benefit_myr"] != 999999.99
    assert result["notice_period_status"] == "employer owes payment in lieu of notice"
    assert result["eis_eligibility"]["likely_eligible"] is True
    assert result["checklist"] == ["Custom step"]
    assert result["warnings"] == ["Custom warning"]
    assert result["status"] == "completed"
    assert len(result["citations"]) == 1


@pytest.mark.asyncio
async def test_output_node_falls_back_when_llm_unavailable():
    state = {
        "years_of_service": 1.0,
        "monthly_salary_myr": 2600.0,
        "notice_given_days": 30,
        "is_eis_contributor": False,
        "language": "bm",
        "_rag_findings": [],
    }
    with patch("app.agents.retrenchment_navigator.nodes.llm_complete", AsyncMock(return_value="")):
        result = await output_node(state)

    assert result["checklist"]  # falls back to the static default list
    assert result["warnings"]
    assert result["notice_period_status"] == "sufficient"  # 30 given >= 28 (4 weeks) minimum for <2y


@pytest.mark.asyncio
async def test_output_node_handles_missing_years_or_salary():
    state = {"language": "en", "_rag_findings": []}
    with patch("app.agents.retrenchment_navigator.nodes.llm_complete", AsyncMock(return_value="")):
        result = await output_node(state)
    assert result["statutory_benefits"] == {}
    assert result["notice_period_status"] == "unknown"


# ── Graph wiring ─────────────────────────────────────────────────────────────

def test_retrenchment_navigator_graph_compiles():
    from langgraph.checkpoint.memory import MemorySaver

    g = build_retrenchment_navigator_graph().compile(checkpointer=MemorySaver())
    assert g is not None


# ── Router dispatch (mirrors test_agents_wired.py's pattern) ────────────────

def _auth_header(plan: str = "free") -> dict[str, str]:
    token = jwt.encode(
        {"sub": "u1", "aud": settings.supabase_jwt_aud, "app_metadata": {"plan": plan}},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _client() -> TestClient:
    from app.routers import agents as agents_router

    app = FastAPI()
    app.include_router(agents_router.router)
    from langgraph.checkpoint.memory import MemorySaver

    app.state.checkpointer = MemorySaver()
    app.state.supabase = None
    load_agent_registry(None)
    return TestClient(app)


def test_retrenchment_navigator_registered_in_agent_list():
    res = _client().get("/api/v1/agents", headers=_auth_header("pro"))
    assert res.status_code == 200
    names = {a["name"] for a in res.json()}
    assert "retrenchment-navigator" in names


def test_retrenchment_navigator_start_free_plan_allowed():
    from app.routers import agents as agents_router

    fake = AsyncMock(return_value={
        "session_id": "r1",
        "status": "needs_input",
        "next_prompt": "How many years have you worked for this employer?",
        "output": {},
    })
    with patch.object(agents_router, "AGENT_START_HANDLERS", {"retrenchment-navigator": fake}):
        res = _client().post(
            "/api/v1/agents/retrenchment-navigator/start",
            json={"message": "I was retrenched"},
            headers=_auth_header("free"),
        )
    assert res.status_code == 200
    assert res.json()["status"] == "needs_input"


def test_retrenchment_navigator_start_401_without_auth():
    res = _client().post("/api/v1/agents/retrenchment-navigator/start", json={"message": "hi"})
    assert res.status_code == 401
