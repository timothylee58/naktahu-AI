"""Tests for the JWT-authenticated developer key routes (routers/developer.py).

Public-API key auth and the /api/v1/public/* endpoints are already covered by
test_api_keys.py; this file covers the key-management routes it does not:
auth boundary, validation, degraded mode (503), and the revoke path.

The service layer is patched, so no Supabase is needed. The app under test is
app.main (what Railway deploys) — root main.py does not mount this router.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

KEY_ROW = {
    "id": "key-1",
    "key_prefix": "nk_live_abcd1234",
    "plan": "starter",
    "calls_used": 3,
    "calls_limit": 5500,
    "rate_limit_per_min": 10,
    "domain_whitelist": [],
    "active": True,
    "last_used_at": None,
    "created_at": "2026-01-01T00:00:00Z",
}


@pytest.fixture
def dev_client():
    """TestClient with a stand-in Supabase client on app.state (no lifespan)."""
    previous = getattr(app.state, "supabase", None)
    app.state.supabase = MagicMock()
    yield TestClient(app)
    app.state.supabase = previous


def test_list_keys_requires_auth(dev_client):
    assert dev_client.get("/api/v1/developer/keys").status_code == 401


def test_create_key_requires_auth(dev_client):
    res = dev_client.post("/api/v1/developer/keys", json={"plan": "starter"})
    assert res.status_code == 401


def test_list_keys_returns_public_fields_only(dev_client, auth_headers):
    with patch("routers.developer.list_api_keys", new=AsyncMock(return_value=[KEY_ROW])):
        res = dev_client.get("/api/v1/developer/keys", headers=auth_headers)
    assert res.status_code == 200
    keys = res.json()["keys"]
    assert keys[0]["id"] == "key-1"
    assert keys[0]["key_prefix"] == "nk_live_abcd1234"
    assert "key_hash" not in keys[0]
    assert "raw_key" not in keys[0]


def test_create_key_returns_raw_key_once(dev_client, auth_headers):
    created = AsyncMock(return_value=("nk_live_rawsecret", KEY_ROW))
    with patch("routers.developer.create_api_key_record", new=created):
        res = dev_client.post(
            "/api/v1/developer/keys", json={"plan": "starter"}, headers=auth_headers
        )
    assert res.status_code == 201
    assert res.json()["raw_key"] == "nk_live_rawsecret"
    assert created.await_args.kwargs["user_id"] == "test-user-1"


def test_create_key_rejects_unknown_plan(dev_client, auth_headers):
    res = dev_client.post(
        "/api/v1/developer/keys", json={"plan": "platinum"}, headers=auth_headers
    )
    assert res.status_code == 422


def test_create_key_rejects_oversized_domain_whitelist(dev_client, auth_headers):
    res = dev_client.post(
        "/api/v1/developer/keys",
        json={"plan": "starter", "domain_whitelist": [f"d{i}.example" for i in range(11)]},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_create_key_max_keys_maps_to_400(dev_client, auth_headers):
    maxed = AsyncMock(side_effect=ValueError("max_keys_reached"))
    with patch("routers.developer.create_api_key_record", new=maxed):
        res = dev_client.post(
            "/api/v1/developer/keys", json={"plan": "starter"}, headers=auth_headers
        )
    assert res.status_code == 400


def test_delete_key_success_is_204(dev_client, auth_headers):
    with patch("routers.developer.revoke_api_key", new=AsyncMock(return_value=True)):
        res = dev_client.delete("/api/v1/developer/keys/key-1", headers=auth_headers)
    assert res.status_code == 204


def test_delete_key_not_owned_is_404(dev_client, auth_headers):
    with patch("routers.developer.revoke_api_key", new=AsyncMock(return_value=False)):
        res = dev_client.delete("/api/v1/developer/keys/someone-elses", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/api/v1/developer/keys", None),
        ("post", "/api/v1/developer/keys", {"plan": "starter"}),
        ("delete", "/api/v1/developer/keys/key-1", None),
        ("get", "/api/v1/developer/usage", None),
    ],
)
def test_degraded_mode_returns_503(dev_client, auth_headers, method, path, body):
    app.state.supabase = None
    res = dev_client.request(method, path, json=body, headers=auth_headers)
    assert res.status_code == 503
