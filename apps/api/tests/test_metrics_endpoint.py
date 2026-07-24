"""Tests for the Prometheus /metrics endpoint and its dual-write wiring."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi.testclient import TestClient

import main as api_main
from app.main import app as deploy_app
from app.orchestration.metrics import record_agent_call
from core.config import settings


# ── Router mounted in both mains (CLAUDE.md Trap #1) ────────────────────────


def test_metrics_route_mounted_in_both_mains() -> None:
    # A live request, not app.routes introspection: app.routes' internal
    # shape (whether entries expose .path directly, are nested, etc.) is a
    # FastAPI/Starlette-version implementation detail — this repo pins no
    # exact version (pyproject.toml: "fastapi>=0.115.0,<1.0"), so CI can
    # resolve a different one than a local sandbox. A 404 means the route
    # isn't mounted; anything else (401 here, since no token is sent) means
    # it is — that's true regardless of internal representation.
    assert TestClient(api_main.app).get("/metrics").status_code != 404
    assert TestClient(deploy_app).get("/metrics").status_code != 404


# ── Auth boundary ────────────────────────────────────────────────────────────


def test_metrics_requires_token(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "metrics_auth_token", "sekret-token")
    resp = client.get("/metrics")
    assert resp.status_code == 401


def test_metrics_rejects_wrong_token(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "metrics_auth_token", "sekret-token")
    resp = client.get("/metrics", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_metrics_fails_closed_when_unconfigured(client, monkeypatch) -> None:
    """An empty/unset token means the endpoint always 401s — never fail open."""
    monkeypatch.setattr(settings, "metrics_auth_token", "")
    resp = client.get("/metrics", headers={"Authorization": "Bearer anything"})
    assert resp.status_code == 401


def test_metrics_accepts_correct_token(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "metrics_auth_token", "sekret-token")
    resp = client.get("/metrics", headers={"Authorization": "Bearer sekret-token"})
    assert resp.status_code == 200


# ── Content ──────────────────────────────────────────────────────────────────


def test_metrics_response_shape(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "metrics_auth_token", "sekret-token")
    resp = client.get("/metrics", headers={"Authorization": "Bearer sekret-token"})

    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    assert "naktahu_http_requests_total" in body
    assert "naktahu_agent_calls_total" in body
    assert "naktahu_circuit_breaker_state" in body


def test_metrics_reflects_recorded_agent_call(client, monkeypatch) -> None:
    """Confirms the dual-write wiring, not just that the module imports cleanly."""
    monkeypatch.setattr(settings, "metrics_auth_token", "sekret-token")
    record_agent_call("probe-agent-xyz", success=True, latency_ms=42.0, confidence=0.9)

    resp = client.get("/metrics", headers={"Authorization": "Bearer sekret-token"})

    body = resp.text
    assert 'naktahu_agent_calls_total{agent_name="probe-agent-xyz",result="success"}' in body


def test_metrics_circuit_breaker_collector_fires_without_activity(client, monkeypatch) -> None:
    """The lazy Collector must yield a value even for a breaker that's never tripped."""
    monkeypatch.setattr(settings, "metrics_auth_token", "sekret-token")
    resp = client.get("/metrics", headers={"Authorization": "Bearer sekret-token"})

    body = resp.text
    assert 'naktahu_circuit_breaker_state{provider="ilmu"}' in body


# ── Executor wiring: record_agent_call actually gets invoked ────────────────


@pytest.mark.asyncio
async def test_executor_records_metric_on_no_adapter(monkeypatch) -> None:
    from app.orchestration.orchestrator.executor_node import _execute_single_task

    recorded = MagicMock()
    monkeypatch.setattr("app.orchestration.orchestrator.executor_node.record_agent_call", recorded)
    monkeypatch.setattr("app.orchestration.orchestrator.executor_node.get_adapter", lambda name: None)

    await _execute_single_task({"target_agent": "no-such-agent", "task_id": "t1"}, {})

    recorded.assert_called_once_with("no-such-agent", success=False, latency_ms=0.0)


@pytest.mark.asyncio
async def test_executor_records_metric_on_timeout(monkeypatch) -> None:
    import asyncio

    from app.orchestration.orchestrator.executor_node import _execute_single_task

    recorded = MagicMock()
    monkeypatch.setattr("app.orchestration.orchestrator.executor_node.record_agent_call", recorded)

    adapter = MagicMock()

    async def _hang(context):
        await asyncio.sleep(10)

    adapter.start = _hang
    monkeypatch.setattr("app.orchestration.orchestrator.executor_node.get_adapter", lambda name: adapter)
    monkeypatch.setattr(
        "app.orchestration.orchestrator.executor_node._build_agent_context",
        lambda task, state, shared: MagicMock(timeout_seconds=0.01),
    )

    await _execute_single_task({"target_agent": "slow-agent", "task_id": "t1"}, {})

    assert recorded.call_count == 1
    args, kwargs = recorded.call_args
    assert args[0] == "slow-agent"
    assert kwargs["timeout"] is True


@pytest.mark.asyncio
async def test_executor_records_metric_on_success(monkeypatch) -> None:
    from app.orchestration.orchestrator.executor_node import _execute_single_task
    from app.orchestration.types import AgentResult, AgentStatusEnum

    recorded = MagicMock()
    monkeypatch.setattr("app.orchestration.orchestrator.executor_node.record_agent_call", recorded)

    adapter = MagicMock()
    adapter.start = AsyncMock(
        return_value=AgentResult(
            session_id="s1",
            agent_name="ok-agent",
            status=AgentStatusEnum.completed,
            confidence=0.8,
            latency_ms=15.0,
            cache_hit=True,
            tokens_used=100,
        )
    )
    monkeypatch.setattr("app.orchestration.orchestrator.executor_node.get_adapter", lambda name: adapter)
    monkeypatch.setattr(
        "app.orchestration.orchestrator.executor_node._build_agent_context",
        lambda task, state, shared: MagicMock(timeout_seconds=30.0),
    )

    await _execute_single_task({"target_agent": "ok-agent", "task_id": "t1"}, {})

    recorded.assert_called_once_with(
        "ok-agent",
        success=True,
        latency_ms=15.0,
        confidence=0.8,
        flagged=False,
        cache_hit=True,
        tokens_used=100,
    )
