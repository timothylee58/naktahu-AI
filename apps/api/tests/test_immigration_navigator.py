"""Tests for Immigration Navigator's expanded workflow — the original
general-visa intake path (regression coverage: byte-for-byte unchanged
behaviour), the new named-e-service reference track, and the new SPO
enquiry-drafting track."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.checkpointer import reset_checkpointer_for_tests
from core.config import settings
from app.agents.immigration_navigator.graph import build_immigration_navigator_graph
from app.agents.immigration_navigator.nodes import (
    detect_service_type,
    intake_node,
    is_spo_request,
    output_node,
    route_after_intake,
    route_after_service_detection,
    route_after_service_intake,
    route_after_spo_intake,
    service_intake_node,
    service_output_node,
    service_router_node,
    spo_intake_node,
    spo_output_node,
)
from services.agent_registry import load_agent_registry


@pytest.fixture(autouse=True)
def _reset_cp():
    reset_checkpointer_for_tests()
    yield
    reset_checkpointer_for_tests()


# ── Original general-visa intake path — unchanged regression coverage ──────

@pytest.mark.asyncio
async def test_intake_node_extracts_fields_unchanged():
    state = {"message": "I am from Japan, here for work, staying 12 months.", "messages": [], "turns_count": 0}
    result = await intake_node(state)
    assert result["nationality"] == "japan"
    assert result["purpose"] == "work"
    assert result["duration_months"] == 12
    assert result["intake_complete"] is True


def test_route_after_intake_unchanged():
    assert route_after_intake({"intake_complete": True}) == "immigration_rag"
    assert route_after_intake({"intake_complete": False}) == "__end__"


@pytest.mark.asyncio
async def test_output_node_never_fabricates_citations_without_findings():
    with patch("app.agents.immigration_navigator.nodes.llm_complete", AsyncMock(return_value="")):
        result = await output_node({"purpose": "work", "language": "en", "_rag_findings": []})
    assert result["citations"] == []
    assert result["visa_type"] == "Employment Pass (EP)"


# ── service_router_node — classification + no-op after turn 1 ─────────────

def test_detect_service_type():
    assert detect_service_type("I need to submit my MDAC before arrival") == "mdac"
    assert detect_service_type("How do I renew my PLKS?") == "eplks"
    assert detect_service_type("Applying for MM2H") == "mm2h"
    assert detect_service_type("Check my foreign maid status") == "foreign_worker"
    assert detect_service_type("I want to renew passport") == "passport"
    assert detect_service_type("Interested in PVIP") == "pvip"
    assert detect_service_type("just a random question") is None


def test_is_spo_request():
    assert is_spo_request("I want to submit an SPO enquiry") is True
    assert is_spo_request("I have a complaint about my visa") is True
    assert is_spo_request("Applying for MM2H") is False


@pytest.mark.asyncio
async def test_service_router_classifies_on_first_turn():
    result = await service_router_node({"message": "I need to submit my MDAC", "turns_count": 0})
    assert result == {"service_type": "mdac"}


@pytest.mark.asyncio
async def test_service_router_classifies_spo_over_service_keywords():
    result = await service_router_node({"message": "I want to file an SPO complaint about my PLKS", "turns_count": 0})
    assert result == {"service_type": "spo"}


@pytest.mark.asyncio
async def test_service_router_is_noop_after_turn_one():
    """Cursor-Bugbot-style regression guard: a later field-answer message
    (e.g. an MM2H income figure) must never re-classify and silently
    reassign an in-progress conversation to a different track."""
    result = await service_router_node({"message": "RM50000", "turns_count": 2})
    assert result == {}


def test_route_after_service_detection():
    assert route_after_service_detection({"service_type": "spo"}) == "spo_intake"
    assert route_after_service_detection({"service_type": "mdac"}) == "service_intake"
    assert route_after_service_detection({"service_type": None}) == "intake"
    assert route_after_service_detection({}) == "intake"


# ── service_intake_node / service_output_node ──────────────────────────────

@pytest.mark.asyncio
async def test_service_intake_collects_fields_across_turns():
    state = {"service_type": "mdac", "message": "I want to submit my MDAC", "messages": [], "turns_count": 0, "service_fields": {}}
    r1 = await service_intake_node(state)
    assert r1["intake_complete"] is False
    assert r1["next_prompt"] == "Full name, exactly as printed in your passport"

    state2 = {**state, **r1, "message": "Tan Ah Kow"}
    r2 = await service_intake_node(state2)
    assert r2["service_fields"]["full_name"] == "Tan Ah Kow"
    assert r2["next_prompt"] == "Passport number"


@pytest.mark.asyncio
async def test_service_intake_completes_after_max_turns_even_if_incomplete():
    state = {"service_type": "mdac", "message": "MDAC please", "messages": [], "turns_count": 7, "service_fields": {}}
    result = await service_intake_node(state)
    assert result["turns_count"] == 8
    assert result["intake_complete"] is True


def test_route_after_service_intake():
    assert route_after_service_intake({"intake_complete": True}) == "service_output"
    assert route_after_service_intake({"intake_complete": False}) == "__end__"


@pytest.mark.asyncio
async def test_service_output_never_claims_to_submit_anything():
    state = {
        "service_type": "mdac",
        "language": "en",
        "service_fields": {"full_name": "Tan Ah Kow", "passport_number": "A1234567"},
    }
    with patch("app.agents.immigration_navigator.nodes.query_rag_findings", AsyncMock(return_value=[])):
        result = await service_output_node(state)

    assert result["portal_url"] == "https://imigresen-online.imi.gov.my/mdac/main"
    assert any("does not submit" in w for w in result["warnings"])
    assert result["prefilled_reference"][0] == {"field": "Full name, exactly as printed in your passport", "value": "Tan Ah Kow"}
    assert result["status"] == "completed"


def test_service_output_excludes_lookalike_domain():
    """The known phishing-pattern domain (eservices.imi.gov.my.esarvice.online,
    which surfaced during WebSearch) must never appear in any registered
    portal URL."""
    from app.agents.immigration_navigator.nodes import SERVICE_PORTALS
    for service in SERVICE_PORTALS.values():
        assert "esarvice.online" not in service["url"]


# ── spo_intake_node / spo_output_node ──────────────────────────────────────

@pytest.mark.asyncio
async def test_spo_intake_classifies_category():
    state = {"message": "My PLKS status enquiry", "messages": [], "turns_count": 0}
    result = await spo_intake_node(state)
    assert result["enquiry_category"] == "foreign_worker_plks"
    assert result["intake_complete"] is False  # needs one more detail turn


@pytest.mark.asyncio
async def test_spo_intake_completes_after_second_message():
    state = {"message": "more detail here", "messages": ["My PLKS status enquiry"], "turns_count": 1}
    result = await spo_intake_node(state)
    assert result["intake_complete"] is True


def test_route_after_spo_intake():
    assert route_after_spo_intake({"intake_complete": True}) == "spo_output"
    assert route_after_spo_intake({"intake_complete": False}) == "__end__"


@pytest.mark.asyncio
async def test_spo_output_falls_back_to_verbatim_when_llm_unavailable():
    state = {"messages": ["My PLKS status enquiry", "It expired last week"], "enquiry_category": "foreign_worker_plks", "language": "en"}
    with patch("app.agents.immigration_navigator.nodes.llm_complete", AsyncMock(return_value="")):
        result = await spo_output_node(state)
    assert "PLKS" in result["enquiry_draft"]
    assert any("eapp.imi.gov.my/spo" in c for c in result["checklist"])
    assert any("does not submit" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_spo_output_never_invents_facts_llm_says():
    state = {"messages": ["enquiry"], "enquiry_category": "general", "language": "en"}
    with patch(
        "app.agents.immigration_navigator.nodes.llm_complete",
        AsyncMock(return_value='{"draft": "Dear JIM, regarding my case number FAKE-12345..."}'),
    ):
        result = await spo_output_node(state)
    # The node itself doesn't fabricate — it only relays what the (mocked)
    # LLM returned; this test documents that pass-through, not a guarantee
    # against LLM hallucination (that's the prompt's job, asserted by the
    # "do not invent facts" instruction in spo_output_node itself).
    assert result["enquiry_draft"].startswith("Dear JIM")


# ── Graph wiring ─────────────────────────────────────────────────────────

def test_immigration_navigator_graph_compiles():
    from langgraph.checkpoint.memory import MemorySaver

    g = build_immigration_navigator_graph().compile(checkpointer=MemorySaver())
    assert g is not None


@pytest.mark.asyncio
async def test_graph_routes_mdac_message_to_service_track_end_to_end():
    from langgraph.checkpoint.memory import MemorySaver

    g = build_immigration_navigator_graph().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    with patch("app.agents.immigration_navigator.nodes.query_rag_findings", AsyncMock(return_value=[])):
        result = await g.ainvoke(
            {"message": "I need to submit my MDAC", "language": "en", "turns_count": 0, "service_type": None},
            config=config,
        )
    assert result["service_type"] == "mdac"
    assert result["status"] == "needs_input"
    assert result.get("portal_url") is None  # service_output never ran — intake incomplete


@pytest.mark.asyncio
async def test_graph_still_routes_general_message_to_original_path():
    from langgraph.checkpoint.memory import MemorySaver

    g = build_immigration_navigator_graph().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "t2"}}
    with patch("app.agents.immigration_navigator.nodes.query_rag_findings", AsyncMock(return_value=[])), patch(
        "app.agents.immigration_navigator.nodes.llm_complete", AsyncMock(return_value="")
    ):
        result = await g.ainvoke(
            {"message": "I am from Japan, here for work, staying 12 months.", "language": "en", "turns_count": 0, "service_type": None},
            config=config,
        )
    assert result.get("service_type") is None
    assert result["status"] == "completed"
    assert result["visa_type"] == "Employment Pass (EP)"


# ── Router dispatch — registration only (start/continue handlers already
# covered by test_agents_wired.py's existing immigration-navigator tests) ──

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


def test_immigration_navigator_still_registered_in_agent_list():
    res = _client().get("/api/v1/agents", headers=_auth_header("pro"))
    assert res.status_code == 200
    names = {a["name"] for a in res.json()}
    assert "immigration-navigator" in names
