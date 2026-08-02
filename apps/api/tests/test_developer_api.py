"""Tests for Developer API key management (routers/developer.py).

Rewritten against the real, live, frontend-verified contract — see git
history for the original version, which asserted an API shape that never
existed (different route paths, response field names, auth header, and a
per-plan quota that isn't implemented). This file complements
tests/test_api_keys.py (public-query API-key auth boundary, key format,
openapi/docs) rather than duplicating it — this file covers the
authenticated developer-facing key CRUD flow: list, create, quota, revoke.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.config import settings
from services.api_key_service import API_KEY_RAW_PREFIX, MAX_KEYS_PER_USER


def _auth_header(sub: str = "dev-user-1", plan: str | None = None) -> dict[str, str]:
    payload: dict = {"sub": sub, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600}
    if plan is not None:
        payload["app_metadata"] = {"plan": plan}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    redis_client.incr = AsyncMock(return_value=1)
    redis_client.expire = AsyncMock(return_value=True)
    redis_client.get = AsyncMock(return_value=None)

    def fake_from_url(*args, **kwargs):
        return redis_client

    import app.main as api_main

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    sb = MagicMock()
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    with TestClient(app) as c:
        yield c, sb


def _key_row(**overrides) -> dict:
    row = {
        "id": "key-uuid-1",
        "key_hash": "hash-value",
        "key_prefix": f"{API_KEY_RAW_PREFIX}abc12345",
        "plan": "starter",
        "calls_used": 0,
        "calls_limit": 5500,
        "rate_limit_per_min": 10,
        "domain_whitelist": [],
        "active": True,
        "last_used_at": None,
        "created_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


# ── Authentication boundary ─────────────────────────────────────────────────


def test_list_keys_requires_authentication(client) -> None:
    c, _ = client
    res = c.get("/api/v1/developer/keys")
    assert res.status_code == 401
    assert res.json()["detail"] == "Not authenticated"


def test_create_key_requires_authentication(client) -> None:
    c, _ = client
    res = c.post("/api/v1/developer/keys", json={"plan": "starter"})
    assert res.status_code == 401


def test_revoke_key_requires_authentication(client) -> None:
    c, _ = client
    res = c.delete("/api/v1/developer/keys/key-uuid-1")
    assert res.status_code == 401


# ── List ─────────────────────────────────────────────────────────────────────


def test_list_keys_authenticated_returns_rows_without_raw_key(client) -> None:
    c, sb = client
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=[_key_row()]
    )

    res = c.get("/api/v1/developer/keys", headers=_auth_header())

    assert res.status_code == 200
    data = res.json()
    assert data["keys"][0]["id"] == "key-uuid-1"
    assert data["keys"][0]["key_prefix"].startswith(API_KEY_RAW_PREFIX)
    assert "raw_key" not in data["keys"][0]
    assert "key_hash" not in data["keys"][0]


def test_list_keys_empty(client) -> None:
    c, sb = client
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])

    res = c.get("/api/v1/developer/keys", headers=_auth_header())

    assert res.status_code == 200
    assert res.json()["keys"] == []


# ── Create ───────────────────────────────────────────────────────────────────


def test_create_key_returns_raw_key_once(client) -> None:
    c, sb = client
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(count=0)
    sb.table.return_value.insert.return_value.select.return_value.execute.return_value = MagicMock(data=[_key_row()])

    res = c.post("/api/v1/developer/keys", json={"plan": "starter"}, headers=_auth_header(plan="pro"))

    assert res.status_code == 201
    data = res.json()
    assert data["raw_key"].startswith(API_KEY_RAW_PREFIX)
    assert "key_hash" not in data["key"]
    assert data["key"]["id"] == "key-uuid-1"


def test_create_key_invalid_plan_rejected(client) -> None:
    c, _ = client
    res = c.post("/api/v1/developer/keys", json={"plan": "not-a-real-plan"}, headers=_auth_header())
    assert res.status_code == 422


def test_create_key_default_plan_is_free(client) -> None:
    """Freemium: the default plan is the free tier, open to any signed-in
    user regardless of app subscription — no Pro requirement to try it."""
    c, sb = client
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(count=0)
    sb.table.return_value.insert.return_value.select.return_value.execute.return_value = MagicMock(
        data=[_key_row(plan="free", calls_limit=500, rate_limit_per_min=5)]
    )

    res = c.post("/api/v1/developer/keys", json={}, headers=_auth_header())

    assert res.status_code == 201
    assert res.json()["key"]["plan"] == "free"


def test_create_paid_plan_rejected_for_free_tier_app_user(client) -> None:
    """Freemium gate: paid Developer API plans (starter/growth/etc.) require
    at least a Pro app subscription — a free-tier app user can still use the
    Developer API, just not the paid plans, and must upgrade via /pricing."""
    c, _ = client
    res = c.post("/api/v1/developer/keys", json={"plan": "starter"}, headers=_auth_header())
    assert res.status_code == 403
    assert "Pro subscription" in res.json()["detail"]


def test_create_key_quota_enforced_flat_across_plans(client) -> None:
    """MAX_KEYS_PER_USER is a flat cap for every plan today — no per-plan tiering."""
    c, sb = client
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        count=MAX_KEYS_PER_USER
    )

    res = c.post("/api/v1/developer/keys", json={"plan": "starter"}, headers=_auth_header(plan="pro"))

    assert res.status_code == 400
    assert "Maximum" in res.json()["detail"]


def test_create_widget_key_accepts_domain_whitelist(client) -> None:
    c, sb = client
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(count=0)
    sb.table.return_value.insert.return_value.select.return_value.execute.return_value = MagicMock(
        data=[_key_row(plan="widget", domain_whitelist=["example.com"])]
    )

    res = c.post(
        "/api/v1/developer/keys",
        json={"plan": "widget", "domain_whitelist": ["example.com"]},
        headers=_auth_header(plan="pro"),
    )

    assert res.status_code == 201
    assert res.json()["key"]["domain_whitelist"] == ["example.com"]


# ── Revoke ───────────────────────────────────────────────────────────────────


def test_revoke_key_succeeds(client) -> None:
    c, sb = client
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "key-uuid-1"}]
    )

    res = c.delete("/api/v1/developer/keys/key-uuid-1", headers=_auth_header())

    assert res.status_code == 204


def test_revoke_key_not_owned_returns_404_not_403(client) -> None:
    """Ownership is enforced by filtering the UPDATE on user_id — a key that
    exists but belongs to someone else looks identical to a nonexistent key,
    which is deliberate: don't reveal to a caller probing key IDs that a
    given ID exists but isn't theirs."""
    c, sb = client
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    res = c.delete("/api/v1/developer/keys/someone-elses-key", headers=_auth_header())

    assert res.status_code == 404
    assert res.json()["detail"] == "API key not found"


def test_revoke_unknown_key_returns_404(client) -> None:
    c, sb = client
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    res = c.delete("/api/v1/developer/keys/does-not-exist", headers=_auth_header())

    assert res.status_code == 404
