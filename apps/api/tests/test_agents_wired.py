"""Tests for wired product agents."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.checkpointer import reset_checkpointer_for_tests
from app.agents.grant_finder.graph import build_grant_finder_graph
from app.agents.health_triage.graph import build_health_triage_graph
from app.agents.immigration_navigator.graph import build_immigration_navigator_graph
from app.agents.study_agent.graph import build_study_agent_graph
from app.agents.tools import extract_questions_from_text
from app.routers import agents as agents_router
from services.agent_registry import load_agent_registry


@pytest.fixture(autouse=True)
def _reset_cp():
    reset_checkpointer_for_tests()
    yield
    reset_checkpointer_for_tests()


def test_extract_questions_from_text() -> None:
    text = "Soalan 1: Apakah peranan Malayan Union?\nSoalan 2: Nyatakan 3 kesan pendudukan Jepun."
    qs = extract_questions_from_text(text)
    assert len(qs) >= 1


@pytest.mark.parametrize("builder", [
    build_study_agent_graph,
    build_immigration_navigator_graph,
    build_health_triage_graph,
    build_grant_finder_graph,
])
def test_agent_graphs_compile(builder) -> None:
    from langgraph.checkpoint.memory import MemorySaver

    g = builder().compile(checkpointer=MemorySaver())
    assert g is not None


def _auth_header(plan: str = "student") -> dict[str, str]:
    import jwt
    from core.config import settings

    token = jwt.encode(
        {"sub": "u1", "aud": settings.supabase_jwt_aud, "app_metadata": {"plan": plan}},
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


def test_list_agents_endpoint() -> None:
    res = _client().get("/api/v1/agents", headers=_auth_header("pro"))
    assert res.status_code == 200
    names = {a["name"] for a in res.json()}
    assert "grant-finder" in names
    assert "health-triage" in names


def test_health_triage_start() -> None:
    fake = AsyncMock(return_value={
        "session_id": "h1",
        "status": "completed",
        "output": {"facility_recommendation": "Klinik Kesihatan", "disclaimer": "Not diagnosis"},
    })
    with patch.object(agents_router, "AGENT_START_HANDLERS", {"health-triage": fake}):
        res = _client().post(
            "/api/v1/agents/health-triage/start",
            json={"message": "demam batuk"},
            headers=_auth_header("free"),
        )
    assert res.status_code == 200


def test_study_agent_requires_student_plan() -> None:
    res = _client().post(
        "/api/v1/agents/study-agent/start",
        json={"paper_text": "Soalan 1: Siapakah Bapa Kemerdekaan?"},
        headers=_auth_header("free"),
    )
    assert res.status_code == 403


def test_grant_finder_start() -> None:
    fake = AsyncMock(return_value={
        "session_id": "g1",
        "status": "completed",
        "output": {"grants": [{"name": "TEKUN", "url": "https://www.tekun.gov.my"}]},
    })
    with patch.object(agents_router, "AGENT_START_HANDLERS", {"grant-finder": fake}):
        res = _client().post(
            "/api/v1/agents/grant-finder/start",
            json={"sector": "fnb", "funding_need": "RM 20000"},
            headers=_auth_header("free"),
        )
    assert res.status_code == 200
