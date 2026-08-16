"""Router-level tests for /api/v1/calendar/* — mirrors test_share.py's
TestClient fixture pattern (mock Redis via api_main.redis_ai.from_url, mock
Supabase via api_main.create_client)."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


def _auth_header(sub: str = "calendar-user") -> dict[str, str]:
    tok = jwt.encode(
        {"sub": sub, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(monkeypatch):
    store: dict[str, str] = {}
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    redis_client.setex = AsyncMock(side_effect=lambda k, ttl, v: store.__setitem__(k, v))
    redis_client.get = AsyncMock(side_effect=lambda k: store.get(k))
    redis_client.delete = AsyncMock(side_effect=lambda k: store.pop(k, None))

    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)

    select_result = MagicMock(data=[])
    table_mock = MagicMock()
    table_mock.select.return_value.limit.return_value.execute.return_value = select_result
    table_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = select_result
    table_mock.select.return_value.eq.return_value.execute.return_value = select_result
    table_mock.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()

    sb = MagicMock()
    sb.table.return_value = table_mock

    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, sb, table_mock, redis_client


def test_connect_requires_auth(client):
    c, *_ = client
    res = c.get("/api/v1/calendar/connect/google")
    assert res.status_code == 401


def test_connect_google_returns_authorize_url(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(settings, "google_calendar_client_id", "gid")
    monkeypatch.setattr(settings, "google_calendar_client_secret", "gsecret")

    res = c.get("/api/v1/calendar/connect/google", headers=_auth_header())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["authorize_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")


def test_connect_returns_503_when_provider_not_configured(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(settings, "google_calendar_client_id", "")
    monkeypatch.setattr(settings, "google_calendar_client_secret", "")

    res = c.get("/api/v1/calendar/connect/google", headers=_auth_header())
    assert res.status_code == 503


def test_connect_rejects_unknown_provider(client):
    c, *_ = client
    res = c.get("/api/v1/calendar/connect/dropbox", headers=_auth_header())
    assert res.status_code == 422


def test_status_requires_auth(client):
    c, *_ = client
    res = c.get("/api/v1/calendar/status")
    assert res.status_code == 401


def test_status_returns_both_providers_disconnected_by_default(client):
    c, *_ = client
    res = c.get("/api/v1/calendar/status", headers=_auth_header())
    assert res.status_code == 200, res.text
    body = res.json()
    providers = {row["provider"]: row for row in body}
    assert set(providers) == {"google", "microsoft"}
    assert all(not row["connected"] for row in providers.values())


def test_status_degraded_when_supabase_unavailable(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(c.app.state, "supabase", None)
    res = c.get("/api/v1/calendar/status", headers=_auth_header())
    assert res.status_code == 503


def test_disconnect_requires_auth(client):
    c, *_ = client
    res = c.delete("/api/v1/calendar/google")
    assert res.status_code == 401


def test_disconnect_happy_path(client, monkeypatch):
    c, sb, table_mock, _redis = client
    # disconnect() reads the connection row first (to best-effort revoke),
    # then deletes it — select().eq().eq().execute() must return no rows so
    # the revoke-call branch is skipped cleanly in this test.
    table_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    res = c.delete("/api/v1/calendar/google", headers=_auth_header())
    assert res.status_code == 204


def test_callback_missing_code_redirects_with_error(client):
    c, *_ = client
    res = c.get("/api/v1/calendar/callback/google", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert "calendar_error=google" in res.headers["location"]


def test_callback_unknown_state_redirects_with_error(client):
    c, *_ = client
    res = c.get(
        "/api/v1/calendar/callback/google?code=abc&state=never-issued",
        follow_redirects=False,
    )
    assert res.status_code in (302, 307)
    assert "calendar_error=google" in res.headers["location"]
