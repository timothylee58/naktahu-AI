"""Tests for the Property Concierge agent — nodes, deterministic lead-tier
scoring, graph wiring, and router dispatch."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.checkpointer import reset_checkpointer_for_tests
from core.config import settings
from app.agents.property_concierge.graph import build_property_concierge_graph
from app.agents.property_concierge.nodes import (
    intake_node,
    output_node,
    property_rag_node,
    route_after_intake,
    score_lead,
)
from services.agent_registry import load_agent_registry


@pytest.fixture(autouse=True)
def _reset_cp():
    reset_checkpointer_for_tests()
    yield
    reset_checkpointer_for_tests()


# ── Deterministic lead-tier scoring ─────────────────────────────────────────

@pytest.mark.parametrize(
    "purpose,location,budget,ptype,bedrooms,expected",
    [
        ("buy", "Petaling Jaya", 500000.0, "condo", 3, "hot"),
        ("rent", "Cheras", 2000.0, None, None, "warm"),
        ("buy", "Cheras", 500000.0, "landed", None, "warm"),
        (None, "Cheras", 500000.0, "condo", 3, "cold"),
        ("buy", None, 500000.0, "condo", 3, "cold"),
        ("buy", "Cheras", None, "condo", 3, "cold"),
        ("buy", "Cheras", 0.0, "condo", 3, "cold"),  # budget must be > 0
    ],
)
def test_score_lead(purpose, location, budget, ptype, bedrooms, expected):
    assert score_lead(purpose, location, budget, ptype, bedrooms) == expected


# ── intake_node ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intake_node_extracts_fields_from_message():
    state = {
        "message": "I want to buy a condo in Petaling Jaya, budget RM650,000, need 3 bedrooms.",
        "messages": [],
        "turns_count": 0,
    }
    result = await intake_node(state)
    assert result["purpose"] == "buy"
    assert result["property_type"] == "condo"
    assert result["location"] == "Petaling Jaya"
    assert result["budget_myr"] == 650000.0
    assert result["bedrooms"] == 3
    assert result["intake_complete"] is True
    assert result["status"] == "intake_done"


@pytest.mark.asyncio
async def test_intake_node_asks_for_missing_field():
    state = {"message": "I want to rent something.", "messages": [], "turns_count": 0}
    result = await intake_node(state)
    assert result["intake_complete"] is False
    assert result["status"] == "needs_input"
    assert result["next_prompt"] is not None


@pytest.mark.asyncio
async def test_intake_node_captures_location_as_reply_when_only_field_left():
    """Once purpose + budget are known, a plain free-text reply to the
    location prompt (no 'in X' phrasing) is captured verbatim."""
    state = {
        "message": "Subang Jaya",
        "messages": ["I want to buy, budget RM400000"],
        "purpose": "buy",
        "budget_myr": 400000.0,
        "location": None,
        "turns_count": 1,
    }
    result = await intake_node(state)
    assert result["location"] == "Subang Jaya"
    assert result["intake_complete"] is True


@pytest.mark.asyncio
async def test_intake_node_completes_after_max_turns_even_if_incomplete():
    state = {"message": "not much info here", "messages": [], "turns_count": 5}
    result = await intake_node(state)
    assert result["turns_count"] == 6
    assert result["intake_complete"] is True


def test_route_after_intake():
    assert route_after_intake({"intake_complete": True}) == "property_rag"
    assert route_after_intake({"intake_complete": False}) == "__end__"
    assert route_after_intake({}) == "__end__"


# ── property_rag_node ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_property_rag_node_queries_property_domain():
    findings = [{"source_url": "https://jkptg.gov.my/a", "summary": "strata info"}]

    async def fake_query(query, domain, language="bm"):
        assert domain == "property"
        return findings

    with patch("app.agents.property_concierge.nodes.query_rag_findings", side_effect=fake_query):
        result = await property_rag_node({"language": "en", "location": "Cheras", "tool_calls": []})

    assert result["_rag_findings"] == findings
    assert result["tool_calls"][0]["domain"] == "property"


# ── output_node ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_output_node_uses_deterministic_lead_tier_not_llm():
    """The LLM only drafts checklist/warnings prose — it must never override
    the deterministic lead_tier, even if it tries to (simulated via a bogus
    field the code must simply ignore)."""
    state = {
        "purpose": "buy",
        "property_type": "condo",
        "location": "Petaling Jaya",
        "budget_myr": 650000.0,
        "bedrooms": 3,
        "language": "en",
        "_rag_findings": [
            {"source_url": "https://jkptg.gov.my/a", "source_title": "Strata guidance", "summary": "s", "similarity": 0.8, "domain": "property"}
        ],
    }
    fake_llm_response = (
        '{"checklist": ["Custom step"], "warnings": ["Custom warning"], "lead_tier": "cold"}'
    )
    with patch("app.agents.property_concierge.nodes.llm_complete", AsyncMock(return_value=fake_llm_response)):
        result = await output_node(state)

    assert result["lead_tier"] == "hot"  # deterministic, ignores the LLM's "cold"
    assert result["checklist"] == ["Custom step"]
    assert result["warnings"] == ["Custom warning"]
    assert result["status"] == "completed"
    assert len(result["citations"]) == 1
    assert "RM650,000" in result["escalation_message"]


@pytest.mark.asyncio
async def test_output_node_falls_back_when_llm_unavailable():
    state = {
        "purpose": "rent",
        "property_type": None,
        "location": "Cheras",
        "budget_myr": 2000.0,
        "bedrooms": None,
        "language": "bm",
        "_rag_findings": [],
    }
    with patch("app.agents.property_concierge.nodes.llm_complete", AsyncMock(return_value="")):
        result = await output_node(state)

    assert result["checklist"]  # falls back to the static default list
    assert result["warnings"]
    assert result["lead_tier"] == "warm"


@pytest.mark.asyncio
async def test_output_node_never_fabricates_citations_without_findings():
    state = {"purpose": None, "location": None, "budget_myr": None, "language": "en", "_rag_findings": []}
    with patch("app.agents.property_concierge.nodes.llm_complete", AsyncMock(return_value="")):
        result = await output_node(state)
    assert result["citations"] == []
    assert result["lead_tier"] == "cold"


# ── Graph wiring ─────────────────────────────────────────────────────────────

def test_property_concierge_graph_compiles():
    from langgraph.checkpoint.memory import MemorySaver

    g = build_property_concierge_graph().compile(checkpointer=MemorySaver())
    assert g is not None


# ── Router dispatch (mirrors test_retrenchment_navigator.py's pattern) ─────

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


def test_property_concierge_registered_in_agent_list():
    res = _client().get("/api/v1/agents", headers=_auth_header("pro"))
    assert res.status_code == 200
    names = {a["name"] for a in res.json()}
    assert "property-concierge" in names


def test_property_concierge_start_free_plan_allowed():
    from app.routers import agents as agents_router

    fake = AsyncMock(return_value={
        "session_id": "p1",
        "status": "needs_input",
        "next_prompt": "Are you looking to buy or rent?",
        "output": {},
    })
    with patch.object(agents_router, "AGENT_START_HANDLERS", {"property-concierge": fake}):
        res = _client().post(
            "/api/v1/agents/property-concierge/start",
            json={"message": "I'm looking for a place"},
            headers=_auth_header("free"),
        )
    assert res.status_code == 200
    assert res.json()["status"] == "needs_input"


def test_property_concierge_start_401_without_auth():
    res = _client().post("/api/v1/agents/property-concierge/start", json={"message": "hi"})
    assert res.status_code == 401


def test_property_concierge_continue_does_not_pass_unexpected_user_id():
    from app.routers import agents as agents_router

    captured_kwargs: dict = {}

    async def fake_continue(**kwargs):
        captured_kwargs.update(kwargs)
        return {"session_id": "p1", "status": "completed", "output": {}}

    with patch.object(agents_router, "AGENT_CONTINUE_HANDLERS", {"property-concierge": fake_continue}):
        res = _client().post(
            "/api/v1/agents/property-concierge/continue",
            json={"session_id": "p1", "message": "continuing"},
            headers=_auth_header("free"),
        )
    assert res.status_code == 200
    assert "user_id" not in captured_kwargs
    assert "supabase_client" in captured_kwargs
