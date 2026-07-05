"""Tests for product-agent infrastructure."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.checkpointer import reset_checkpointer_for_tests
from app.agents.compliance_drafter.graph import build_compliance_drafter_graph
from app.agents.research_synthesiser.graph import build_research_synthesiser_graph
from app.routers import agents as agents_router
from services.agent_registry import AgentDefinition, load_agent_registry


@pytest.fixture(autouse=True)
def _reset_cp():
    reset_checkpointer_for_tests()
    yield
    reset_checkpointer_for_tests()


def test_agent_registry_fallback() -> None:
    reg = load_agent_registry(None)
    assert "compliance-drafter" in reg
    assert reg["compliance-drafter"].credit_cost == 1


def test_compliance_graph_compiles_with_hitl_interrupt() -> None:
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_compliance_drafter_graph().compile(
        checkpointer=MemorySaver(),
        interrupt_before=["generate_pdf"],
    )
    assert graph is not None


def test_research_synthesiser_graph_compiles() -> None:
    graph = build_research_synthesiser_graph().compile()
    assert graph is not None


def _auth_header(sub: str = "agent-user", plan: str = "free") -> dict[str, str]:
    import jwt
    from core.config import settings

    token = jwt.encode(
        {"sub": sub, "aud": settings.supabase_jwt_aud, "app_metadata": {"plan": plan}},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(agents_router.router)
    from langgraph.checkpoint.memory import MemorySaver

    app.state.checkpointer = MemorySaver()
    app.state.supabase = None
    load_agent_registry(None)
    return TestClient(app)


def test_agent_start_unknown_agent() -> None:
    fake_start = AsyncMock(return_value={"session_id": "s1", "status": "awaiting_hitl"})
    with patch.object(agents_router, "start_compliance_drafter", fake_start):
        res = _client().post(
            "/api/v1/agents/unknown-agent/start",
            json={"business_type": "sdn_bhd"},
            headers=_auth_header(),
        )
    assert res.status_code == 404


def test_agent_start_compliance_drafter() -> None:
    fake_start = AsyncMock(
        return_value={
            "session_id": "sess-1",
            "status": "awaiting_hitl",
            "awaiting_hitl": True,
            "report_json": {"sections": []},
            "turns_count": 1,
        }
    )
    with (
        patch.object(agents_router, "start_compliance_drafter", fake_start),
        patch.object(agents_router, "get_credits_remaining", AsyncMock(return_value=5)),
    ):
        res = _client().post(
            "/api/v1/agents/compliance-drafter/start",
            json={"business_type": "sdn_bhd", "domains": ["tax"]},
            headers=_auth_header(),
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["session_id"] == "sess-1"
    assert body["status"] == "awaiting_hitl"


def test_is_credit_exempt_business() -> None:
    from services.agent_registry import is_credit_exempt

    assert is_credit_exempt("business", "compliance-drafter") is True
    assert is_credit_exempt("free", "compliance-drafter") is False
