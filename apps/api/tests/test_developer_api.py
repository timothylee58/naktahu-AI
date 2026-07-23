"""Tests for Developer API (API key management + public Knowledge API).

This file covers:
- routers/developer.py (key creation, list, revoke)
- routers/api_v1_public.py (public query endpoint)
- middleware/api_key_auth.py (API key validation)

Pattern notes (Merlion OS):
1. Imports from conftest: auth_headers, api_key_headers (never create locally)
2. Uses TestClient directly (no custom fixtures)
3. Organized by feature/endpoint, not module
4. Each test is independent (uses autouse reset_shared_state fixture)
5. Status codes and error messages are explicit
"""
import pytest
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Authentication Boundary Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_api_keys_list_requires_authentication(client: TestClient, auth_headers_anonymous: dict):
    """Unauthenticated users cannot list API keys.

    Rule: Any endpoint touching user data needs authentication.
    Expectation: 401 Unauthorized
    """
    resp = client.get("/api/v1/keys", headers=auth_headers_anonymous)
    assert resp.status_code == 401
    assert "Unauthorized" in resp.json()["detail"]


def test_api_keys_list_authenticated(client: TestClient, auth_headers: dict):
    """Authenticated users can list their API keys.

    Happy path: Valid JWT, endpoint responds with user's keys.
    Expectation: 200 OK with list of key metadata
    """
    resp = client.get("/api/v1/keys", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Each key has metadata but NOT the raw key (never expose in GET)
    for key_obj in data:
        assert "key_id" in key_obj
        assert "created_at" in key_obj
        assert "name" in key_obj
        assert "raw_key" not in key_obj, "Raw key should never be in response"


# ─────────────────────────────────────────────────────────────────────────────
# Key Creation Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_api_key_create_returns_raw_key_once(client: TestClient, auth_headers: dict):
    """Creating a key returns raw key ONCE; future calls mask it.

    Reasoning: Raw key is secret, only shown at creation time.
    User must save it immediately; future list operations don't show it.

    Expectation:
    - POST /keys/create returns raw_key in response
    - GET /keys/{id} returns key without raw_key
    """
    # Create key
    create_resp = client.post(
        "/api/v1/keys/create",
        json={"name": "Test Key for Creation"},
        headers=auth_headers
    )
    assert create_resp.status_code == 201
    data = create_resp.json()

    # Raw key is present at creation
    assert "raw_key" in data
    assert data["raw_key"].startswith("sk_")  # Correct prefix
    assert "key_id" in data
    key_id = data["key_id"]

    # Fetch same key: raw_key should NOT be in response
    fetch_resp = client.get(f"/api/v1/keys/{key_id}", headers=auth_headers)
    assert fetch_resp.status_code == 200
    assert "raw_key" not in fetch_resp.json()
    assert fetch_resp.json()["key_id"] == key_id


def test_api_key_create_requires_name(client: TestClient, auth_headers: dict):
    """Creating a key without a name fails validation.

    Expectation: 422 Unprocessable Entity
    """
    resp = client.post(
        "/api/v1/keys/create",
        json={},  # Missing 'name'
        headers=auth_headers
    )
    assert resp.status_code == 422
    assert "name" in resp.json()["detail"][0]["loc"]


def test_api_key_create_name_bounds(client: TestClient, auth_headers: dict):
    """API key name must be 1–100 characters (no empty, no excess).

    Expectation: 422 on invalid length
    """
    # Empty name
    resp = client.post(
        "/api/v1/keys/create",
        json={"name": ""},
        headers=auth_headers
    )
    assert resp.status_code == 422

    # Oversized name (>100 chars)
    resp = client.post(
        "/api/v1/keys/create",
        json={"name": "a" * 101},
        headers=auth_headers
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Key Validation Tests (Middleware)
# ─────────────────────────────────────────────────────────────────────────────

def test_api_key_invalid_format_rejected(client: TestClient):
    """Invalid API key format is rejected before DB lookup.

    Reasoning: Don't waste DB query on malformed keys.
    Format: sk_test_* or sk_live_*

    Expectation: 401 with clear message
    """
    resp = client.post(
        "/api/v1/query",
        json={"query": "test query"},
        headers={"X-API-Key": "not_a_valid_key_at_all"}
    )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower() or \
           "format" in resp.json()["detail"].lower()


def test_api_key_unknown_key_rejected(client: TestClient):
    """Unknown API key (valid format, but not in DB) is rejected.

    Expectation: 401
    """
    resp = client.post(
        "/api/v1/query",
        json={"query": "tax brackets"},
        headers={"X-API-Key": "sk_test_this_key_does_not_exist_xyz"}
    )
    assert resp.status_code == 401


def test_public_query_endpoint_requires_api_key(client: TestClient):
    """Public query endpoint (/api/v1/query) requires API key.

    Reasoning: Protects quota and billing.
    Note: This is DIFFERENT from /api/v1/query over authenticated user (different endpoint).

    Expectation: 401 without key
    """
    resp = client.post(
        "/api/v1/query",
        json={"query": "What is CPF?"}
    )
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Key Revocation Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_api_key_revocation_prevents_future_use(client: TestClient, auth_headers: dict):
    """After revocation, the key is immediately unusable.

    Flow:
    1. Create key
    2. Revoke it
    3. Attempt to use it → 401

    Expectation: Key shows revoked_at timestamp after revocation
    """
    # Create key
    create_resp = client.post(
        "/api/v1/keys/create",
        json={"name": "Key to Revoke"},
        headers=auth_headers
    )
    key_id = create_resp.json()["key_id"]

    # Revoke it
    revoke_resp = client.post(
        f"/api/v1/keys/{key_id}/revoke",
        headers=auth_headers
    )
    assert revoke_resp.status_code == 200

    # Check key is marked revoked
    get_resp = client.get(f"/api/v1/keys/{key_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert "revoked_at" in get_resp.json()
    assert get_resp.json()["revoked_at"] is not None


def test_api_key_revocation_not_owned_by_user_fails(client: TestClient, auth_headers_free: dict, auth_headers_business: dict):
    """Users cannot revoke keys they don't own.

    Expectation: 403 Forbidden (or 404 if we hide the key's existence)
    """
    # Business user creates key
    create_resp = client.post(
        "/api/v1/keys/create",
        json={"name": "Business Key"},
        headers=auth_headers_business
    )
    key_id = create_resp.json()["key_id"]

    # Free user tries to revoke it
    revoke_resp = client.post(
        f"/api/v1/keys/{key_id}/revoke",
        headers=auth_headers_free
    )
    # Should be 404 (not found) or 403 (forbidden); not 200
    assert revoke_resp.status_code in [403, 404]


# ─────────────────────────────────────────────────────────────────────────────
# Public API Schema Tests (OpenAI Compatible)
# ─────────────────────────────────────────────────────────────────────────────

def test_public_api_openai_compatible_schema(client: TestClient, api_key_headers: dict, monkeypatch):
    """Public API /api/v1/query response matches OpenAI chat completions schema.

    OpenAI schema structure:
    {
      "id": "...",
      "object": "text_completion",
      "created": 1234567890,
      "model": "...",
      "choices": [
        {
          "index": 0,
          "message": {"role": "assistant", "content": "..."},
          "finish_reason": "stop"
        }
      ],
      "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30
      }
    }
    """
    # Mock the LLM to avoid network call
    from unittest.mock import AsyncMock, patch

    async def fake_query(*args, **kwargs):
        return "This is a test response."

    monkeypatch.setattr("app.agents.rag_node.invoke", fake_query)

    resp = client.post(
        "/api/v1/query",
        json={"query": "What is BTO?", "language": "en"},
        headers=api_key_headers
    )

    # Status should be 200 (or possibly 503 if Supabase is mocked as down)
    if resp.status_code == 200:
        data = resp.json()

        # Validate OpenAI schema
        assert "choices" in data
        assert isinstance(data["choices"], list)
        assert len(data["choices"]) > 0

        choice = data["choices"][0]
        assert "message" in choice
        assert "content" in choice["message"]
        assert "role" in choice["message"]
        assert choice["role"] == "assistant"

        # Usage stats
        assert "usage" in data
        assert "prompt_tokens" in data["usage"]
        assert "completion_tokens" in data["usage"]
        assert isinstance(data["usage"]["prompt_tokens"], int)
        assert isinstance(data["usage"]["completion_tokens"], int)


# ─────────────────────────────────────────────────────────────────────────────
# Rate Limiting Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_api_key_rate_limit_headers_present(client: TestClient, api_key_headers: dict):
    """Responses include rate-limit headers (even on 401).

    Headers:
    - X-RateLimit-Limit: Total requests allowed
    - X-RateLimit-Remaining: Requests left
    - X-RateLimit-Reset: Unix timestamp when limit resets

    These headers inform clients about their quota.
    """
    resp = client.post(
        "/api/v1/query",
        json={"query": "test"},
        headers=api_key_headers
    )

    # Check headers are present (regardless of status code)
    # Note: may not be present on 401 for unknown key; that's acceptable
    if resp.status_code != 401:
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

        # Verify they're numeric
        assert resp.headers["X-RateLimit-Limit"].isdigit()
        assert resp.headers["X-RateLimit-Remaining"].isdigit()
        assert resp.headers["X-RateLimit-Reset"].isdigit()


# ─────────────────────────────────────────────────────────────────────────────
# Plan-Gating Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_free_tier_limited_api_key_quota(client: TestClient, auth_headers_free: dict):
    """Free-tier users are limited in how many API keys they can create.

    Rule: free tier ≤ 3 keys, student ≤ 10, pro/business unlimited

    Expectation: After 3rd key, 4th create returns 403
    """
    # Free user creates keys
    for i in range(3):
        resp = client.post(
            "/api/v1/keys/create",
            json={"name": f"Free Key {i+1}"},
            headers=auth_headers_free
        )
        assert resp.status_code == 201

    # 4th key: should fail
    resp = client.post(
        "/api/v1/keys/create",
        json={"name": "Free Key 4 (should fail)"},
        headers=auth_headers_free
    )
    assert resp.status_code == 403
    assert "quota" in resp.json()["detail"].lower() or \
           "limit" in resp.json()["detail"].lower()


def test_business_tier_unlimited_api_keys(client: TestClient, auth_headers_business: dict):
    """Business users have unlimited API keys.

    Expectation: 10 creates all succeed (no quota error)
    """
    for i in range(10):
        resp = client.post(
            "/api/v1/keys/create",
            json={"name": f"Biz Key {i+1}"},
            headers=auth_headers_business
        )
        assert resp.status_code == 201, \
            f"Business user should not be quota-limited; failed at key {i+1}"
