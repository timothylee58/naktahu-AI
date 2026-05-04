"""Tests for middleware/user_context.py and middleware/rate_limit.py."""

import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

import main as api_main
from core.config import settings
from middleware.rate_limit import (
    anonymous_limiter,
    authenticated_limiter,
    query_limit_provider,
    query_rate_limit_key,
)
from middleware.user_context import _bearer_token


# ---------------------------------------------------------------------------
# _bearer_token — pure-function unit tests
# ---------------------------------------------------------------------------


def _make_request(headers: dict | None = None) -> Request:
    headers = headers or {}
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def test_bearer_token_no_header_returns_none():
    assert _bearer_token(_make_request()) is None


def test_bearer_token_non_bearer_scheme_returns_none():
    assert _bearer_token(_make_request({"authorization": "Basic dXNlcjpwYXNz"})) is None


def test_bearer_token_empty_value_after_bearer_returns_none():
    assert _bearer_token(_make_request({"authorization": "Bearer "})) is None


def test_bearer_token_whitespace_only_returns_none():
    assert _bearer_token(_make_request({"authorization": "Bearer    "})) is None


def test_bearer_token_valid_extraction():
    assert _bearer_token(_make_request({"authorization": "Bearer my-token-value"})) == "my-token-value"


def test_bearer_token_case_insensitive_scheme():
    assert _bearer_token(_make_request({"authorization": "BEARER my-token"})) == "my-token"


# ---------------------------------------------------------------------------
# query_rate_limit_key and query_limit_provider unit tests
# ---------------------------------------------------------------------------


def _make_request_with_state(user_id: str | None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/query",
        "query_string": b"",
        "headers": [],
    }
    req = Request(scope)
    req.state.user_id = user_id
    return req


def test_query_rate_limit_key_with_user_id():
    req = _make_request_with_state("user-123")
    key = query_rate_limit_key(req)
    assert key == "auth:user-123"


def test_query_rate_limit_key_without_user_id():
    req = _make_request_with_state(None)
    key = query_rate_limit_key(req)
    assert key.startswith("anon:")


def test_query_limit_provider_authenticated_returns_200_per_hour():
    assert query_limit_provider("auth:user-1") == "200/hour"


def test_query_limit_provider_anonymous_returns_30_per_hour():
    assert query_limit_provider("anon:127.0.0.1") == "30/hour"


# ---------------------------------------------------------------------------
# UserContextMiddleware integration via TestClient
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    redis_client.lrange = AsyncMock(return_value=[])

    pipe = MagicMock()
    pipe.lpush.return_value = pipe
    pipe.ltrim.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **kw: redis_client)

    sb = MagicMock()
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c


def _valid_token(sub: str = "mw-user") -> str:
    return jwt.encode(
        {"sub": sub, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )


def test_middleware_no_token_request_is_anonymous(client):
    # Anon bucket: 30/hour. After 30 it's blocked.
    for i in range(30):
        r = client.post("/api/v1/query", json={"query": f"q{i}"})
        assert r.status_code == 200
    blocked = client.post("/api/v1/query", json={"query": "blocked"})
    assert blocked.status_code == 429


def test_middleware_invalid_token_treated_as_anonymous(client):
    for i in range(30):
        client.post("/api/v1/query", json={"query": f"q{i}"})
    # Invalid token → middleware catches InvalidTokenError → user_id=None → anon bucket exhausted
    blocked = client.post(
        "/api/v1/query",
        json={"query": "blocked"},
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert blocked.status_code == 429


def test_middleware_expired_token_treated_as_anonymous(client):
    expired_tok = jwt.encode(
        {"sub": "user-x", "aud": settings.supabase_jwt_aud, "exp": int(time.time()) - 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    for i in range(30):
        client.post("/api/v1/query", json={"query": f"q{i}"})
    # Expired token → middleware catches ExpiredSignatureError → user_id=None → anon bucket exhausted
    blocked = client.post(
        "/api/v1/query",
        json={"query": "blocked"},
        headers={"Authorization": f"Bearer {expired_tok}"},
    )
    assert blocked.status_code == 429


def test_middleware_valid_token_uses_separate_auth_bucket(client):
    # Exhaust anon bucket
    for i in range(30):
        client.post("/api/v1/query", json={"query": f"q{i}"})
    # Authenticated user should use a separate bucket and still succeed
    r = client.post(
        "/api/v1/query",
        json={"query": "auth user"},
        headers={"Authorization": f"Bearer {_valid_token()}"},
    )
    assert r.status_code == 200
