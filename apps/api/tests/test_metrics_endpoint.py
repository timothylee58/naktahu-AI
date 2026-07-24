"""Tests for the Prometheus /metrics endpoint and its dual-write wiring."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import main as api_main
from app.main import app as deploy_app
from app.orchestration.metrics import record_agent_call
from core.config import settings


# ── Router mounted in both mains (CLAUDE.md Trap #1) ────────────────────────


def test_metrics_route_mounted_in_both_mains() -> None:
    # app.routes can contain route types without a .path attribute (e.g. a
    # mounted sub-router wrapper), depending on the installed
    # FastAPI/Starlette version — filter with getattr rather than assuming
    # every entry is a plain APIRoute.
    api_paths = [getattr(r, "path", None) for r in api_main.app.routes]
    deploy_paths = [getattr(r, "path", None) for r in deploy_app.routes]
    assert "/metrics" in api_paths
    assert "/metrics" in deploy_paths


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
