"""Tests for /api/v1/query SSE endpoint and /health endpoint."""

import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


def _auth_header(sub: str = "query-user") -> dict:
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
    redis_client.lrange = AsyncMock(return_value=[])

    pipe = MagicMock()
    pipe.lpush.return_value = pipe
    pipe.ltrim.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_client.pipeline = MagicMock(return_value=pipe)

    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **kw: redis_client)

    sb = MagicMock()
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, redis_client, sb


def test_health_endpoint_returns_ok(client):
    c, *_ = client
    res = c.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_query_anonymous_returns_sse_events(client):
    c, *_ = client
    res = c.post("/api/v1/query", json={"query": "Hello"})
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    body = res.text
    assert "event: token" in body
    assert "event: done" in body


def test_query_sse_done_event_contains_citations(client):
    c, *_ = client
    res = c.post("/api/v1/query", json={"query": "Hello"})
    assert res.status_code == 200
    assert '"citations": []' in res.text


def test_query_empty_query_returns_422(client):
    c, *_ = client
    res = c.post("/api/v1/query", json={"query": ""})
    assert res.status_code == 422


def test_query_missing_query_field_returns_422(client):
    c, *_ = client
    res = c.post("/api/v1/query", json={})
    assert res.status_code == 422


def test_query_custom_language_and_domain_reflected_in_stream(client):
    c, *_ = client
    res = c.post("/api/v1/query", json={"query": "Cukai?", "language": "ms", "domain": "tax"})
    assert res.status_code == 200
    assert "tax" in res.text


def test_query_authenticated_triggers_persist(client):
    c, redis_client, sb = client
    res = c.post("/api/v1/query", json={"query": "What is income tax?"}, headers=_auth_header())
    assert res.status_code == 200
    # persist_session_entry uses a pipeline
    redis_client.pipeline.assert_called()


def test_query_anonymous_does_not_persist(client):
    c, redis_client, sb = client
    res = c.post("/api/v1/query", json={"query": "Hello"})
    assert res.status_code == 200
    redis_client.pipeline.assert_not_called()


def test_query_persist_exception_caught_stream_still_completes(client):
    c, redis_client, sb = client
    pipe = redis_client.pipeline.return_value
    pipe.execute = AsyncMock(side_effect=RuntimeError("Redis down"))

    res = c.post("/api/v1/query", json={"query": "test"}, headers=_auth_header())
    # Stream should complete normally even when persist fails
    assert res.status_code == 200
    assert "event: done" in res.text
