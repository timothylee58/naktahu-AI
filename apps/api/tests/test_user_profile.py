"""Saved profile endpoints: owner-scoped, optional fields, 503 until migration 063."""
import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


def _auth(sub: str = "user-a") -> dict[str, str]:
    tok = jwt.encode(
        {"sub": sub, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)

    table = MagicMock()
    table.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    # select("*").eq("user_id", ...).limit(1)
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table.upsert.return_value.execute.return_value = MagicMock(data=[])
    table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    sb = MagicMock()
    sb.table.return_value = table
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()
    with TestClient(api_main.app) as c:
        yield c, sb, table


def test_anonymous_is_401(client):
    c, _, _ = client
    assert c.get("/api/v1/me/profile").status_code == 401
    assert c.put("/api/v1/me/profile", json={}).status_code == 401
    assert c.delete("/api/v1/me/profile").status_code == 401


def test_get_empty_profile_returns_all_null(client):
    c, _, _ = client
    r = c.get("/api/v1/me/profile", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["state"] is None and body["is_bumiputera"] is None
    assert body["household_size"] is None


def test_get_reads_only_the_callers_row(client):
    c, _, table = client
    row = {"user_id": "user-a", "state": "selangor", "household_size": 4, "is_bumiputera": None,
           "updated_at": "2026-11-27T00:00:00+00:00"}
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[row])
    r = c.get("/api/v1/me/profile", headers=_auth("user-a"))
    assert r.json()["state"] == "selangor" and r.json()["household_size"] == 4
    table.select.return_value.eq.assert_called_with("user_id", "user-a")


def test_put_upserts_for_the_callers_user_id_not_a_body_one(client):
    c, _, table = client
    r = c.put(
        "/api/v1/me/profile",
        headers=_auth("user-a"),
        json={"state": "kl", "postcode": "50000", "employment_status": "employed",
              "business_type": "sdn_bhd", "sector": "technology", "household_size": 3,
              "user_id": "someone-else"},
    )
    assert r.status_code == 200
    payload = table.upsert.call_args.args[0]
    assert payload["user_id"] == "user-a"
    assert payload["state"] == "kl" and payload["is_bumiputera"] is None
    assert table.upsert.call_args.kwargs["on_conflict"] == "user_id"


def test_bumiputera_is_opt_in_and_false_is_kept_distinct_from_not_shared(client):
    c, _, table = client
    c.put("/api/v1/me/profile", headers=_auth(), json={"is_bumiputera": False})
    assert table.upsert.call_args.args[0]["is_bumiputera"] is False
    c.put("/api/v1/me/profile", headers=_auth(), json={})
    assert table.upsert.call_args.args[0]["is_bumiputera"] is None


@pytest.mark.parametrize("bad", [
    {"state": "atlantis"},
    {"postcode": "5000"},
    {"postcode": "abcde"},
    {"employment_status": "astronaut"},
    {"business_type": "dao"},
    {"sector": "alchemy"},
    {"household_size": 0},
    {"household_size": 31},
])
def test_validation_rejects_bad_values(client, bad):
    c, _, _ = client
    assert c.put("/api/v1/me/profile", headers=_auth(), json=bad).status_code == 422


def test_delete_removes_only_the_callers_row(client):
    c, _, table = client
    r = c.delete("/api/v1/me/profile", headers=_auth("user-a"))
    assert r.status_code == 204
    table.delete.return_value.eq.assert_called_with("user_id", "user-a")


def test_503_when_supabase_unavailable(client):
    c, _, _ = client
    api_main.app.state.supabase = None
    try:
        assert c.get("/api/v1/me/profile", headers=_auth()).status_code == 503
        assert c.put("/api/v1/me/profile", headers=_auth(), json={}).status_code == 503
        assert c.delete("/api/v1/me/profile", headers=_auth()).status_code == 503
    finally:
        pass


def test_503_until_migration_applied(client):
    c, _, table = client
    table.select.return_value.eq.return_value.limit.return_value.execute.side_effect = RuntimeError("relation does not exist")
    assert c.get("/api/v1/me/profile", headers=_auth()).status_code == 503
