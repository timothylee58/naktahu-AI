"""Tests for the on-demand Health Triage PDF export — export_health_triage()
in agent_runner.py plus the /api/v1/agents/health-triage/{session_id}/export
router endpoint. Health Triage's graph has no HITL confirm step (unlike
compliance-drafter/grant-draft-generator, which generate their PDF as part
of the graph flow), so this doesn't run the real graph — it mocks
get_health_triage_graph's aget_state() to return a fixed completed-session
snapshot, matching how a genuinely finished session looks.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.agent_runner import _render_health_triage_html, export_health_triage
from app.routers import agents as agents_router
from core.config import settings
from services.agent_registry import load_agent_registry

_COMPLETED_VALUES = {
    "session_id": "h1",
    "user_id": "u1",
    "symptoms": ["demam", "batuk"],
    "severity": "routine",
    "facility_recommendation": "Klinik Kesihatan (KK) untuk rawatan primer.",
    "facilities": [{"type": "klinik_kesihatan", "name": "Klinik Kesihatan", "action": "Walk-in"}],
    "citations": [{"title": "KKM Garis Panduan", "ministry": "KKM", "url": "https://www.moh.gov.my"}],
    "disclaimer": "⚠️ This is NOT a medical diagnosis.",
    "status": "completed",
}


def _fake_snapshot(values: dict | None):
    snap = MagicMock()
    snap.values = values or {}
    return snap


def _fake_graph(values: dict | None):
    graph = MagicMock()
    graph.aget_state = AsyncMock(return_value=_fake_snapshot(values))
    return graph


def test_render_health_triage_html_includes_key_fields():
    rendered = _render_health_triage_html(_COMPLETED_VALUES)
    assert "demam, batuk" in rendered
    assert "Klinik Kesihatan (KK)" in rendered
    assert "KKM Garis Panduan" in rendered
    assert "NOT a medical diagnosis" in rendered


def test_render_health_triage_html_escapes_user_supplied_symptoms():
    """Symptoms come from free-text intake — must not let a symptom
    containing HTML break the rendered document structure."""
    values = {**_COMPLETED_VALUES, "symptoms": ["<script>alert(1)</script>"]}
    rendered = _render_health_triage_html(values)
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_render_health_triage_html_omits_citation_without_url():
    """Confirmed CodeRabbit finding: a citation-shaped entry with a title
    but no source url must not be rendered as if it were a real,
    verified source (CLAUDE.md's citation rule)."""
    values = {
        **_COMPLETED_VALUES,
        "citations": [
            {"title": "Has URL", "ministry": "KKM", "url": "https://www.moh.gov.my"},
            {"title": "No URL", "ministry": "KKM"},
        ],
    }
    rendered = _render_health_triage_html(values)
    assert "Has URL" in rendered
    assert "No URL" not in rendered


@pytest.mark.asyncio
async def test_export_health_triage_raises_on_missing_session():
    with patch("app.services.agent_runner.get_health_triage_graph", return_value=_fake_graph(None)):
        with pytest.raises(ValueError):
            await export_health_triage(
                session_id="missing", checkpointer=None, supabase_client=MagicMock(), user_id="u1"
            )


@pytest.mark.asyncio
async def test_export_health_triage_raises_when_not_yet_completed():
    incomplete = {"session_id": "h1", "symptoms": ["demam"]}  # no facility_recommendation yet
    with patch("app.services.agent_runner.get_health_triage_graph", return_value=_fake_graph(incomplete)):
        with pytest.raises(ValueError):
            await export_health_triage(
                session_id="h1", checkpointer=None, supabase_client=MagicMock(), user_id="u1"
            )


@pytest.mark.asyncio
async def test_export_health_triage_raises_for_non_owner():
    """Confirmed Cursor Bugbot/security finding: session_id alone is not
    ownership proof — a different authenticated user requesting export
    of u1's session must be rejected, and with the same ValueError as a
    genuinely missing session (not a distinct error) so the response
    doesn't confirm the session_id is valid for someone else."""
    with patch("app.services.agent_runner.get_health_triage_graph", return_value=_fake_graph(_COMPLETED_VALUES)):
        with pytest.raises(ValueError):
            await export_health_triage(
                session_id="h1", checkpointer=None, supabase_client=MagicMock(), user_id="someone-else"
            )


@pytest.mark.asyncio
async def test_export_health_triage_success_persists_document():
    sb = MagicMock()
    with (
        patch("app.services.agent_runner.get_health_triage_graph", return_value=_fake_graph(_COMPLETED_VALUES)),
        patch(
            "app.agents.tools.generate_pdf",
            AsyncMock(return_value=("agents/health-triage/u1/x.pdf", "https://signed.example/x.pdf", "2024-01-02T00:00:00Z")),
        ),
    ):
        result = await export_health_triage(
            session_id="h1", checkpointer=None, supabase_client=sb, user_id="u1"
        )

    assert result["signed_url"] == "https://signed.example/x.pdf"
    assert result["pdf_storage_path"] == "agents/health-triage/u1/x.pdf"
    sb.table.assert_called_with("generated_documents")
    inserted = sb.table.return_value.insert.call_args[0][0]
    assert inserted["agent_type"] == "health-triage"
    assert inserted["user_id"] == "u1"


# ── router: POST /api/v1/agents/health-triage/{session_id}/export ────────

def _auth_header(plan: str = "free") -> dict[str, str]:
    token = jwt.encode(
        {"sub": "u1", "aud": settings.supabase_jwt_aud, "app_metadata": {"plan": plan}},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _client(supabase: object | None) -> TestClient:
    app = FastAPI()
    app.include_router(agents_router.router)
    from langgraph.checkpoint.memory import MemorySaver

    app.state.checkpointer = MemorySaver()
    app.state.supabase = supabase
    load_agent_registry(None)
    return TestClient(app)


def test_export_endpoint_401_without_auth():
    res = _client(MagicMock()).post("/api/v1/agents/health-triage/h1/export")
    assert res.status_code == 401


def test_export_endpoint_503_when_supabase_degraded():
    res = _client(None).post("/api/v1/agents/health-triage/h1/export", headers=_auth_header())
    assert res.status_code == 503


def test_export_endpoint_404_when_session_not_found():
    with patch.object(
        agents_router,
        "export_health_triage",
        AsyncMock(side_effect=ValueError("session not found")),
    ):
        res = _client(MagicMock()).post("/api/v1/agents/health-triage/missing/export", headers=_auth_header())
    assert res.status_code == 404


def test_export_endpoint_200_on_success():
    fake = AsyncMock(return_value={
        "pdf_storage_path": "agents/health-triage/u1/x.pdf",
        "signed_url": "https://signed.example/x.pdf",
        "url_expires_at": "2024-01-02T00:00:00Z",
    })
    with patch.object(agents_router, "export_health_triage", fake):
        res = _client(MagicMock()).post("/api/v1/agents/health-triage/h1/export", headers=_auth_header())
    assert res.status_code == 200, res.text
    assert res.json()["signed_url"] == "https://signed.example/x.pdf"
