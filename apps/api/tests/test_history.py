import json
import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


def _auth_header(sub: str = "hist-user", plan: str = "pro") -> dict[str, str]:
    tok = jwt.encode(
        {
            "sub": sub,
            "aud": settings.supabase_jwt_aud,
            "exp": int(time.time()) + 3600,
            "app_metadata": {"plan": plan},
        },
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

    def fake_from_url(*args, **kwargs):
        return redis_client

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[{"id": "1"}])
    table_mock = MagicMock()
    table_mock.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.insert.return_value = insert_mock

    sb = MagicMock()
    sb.table.return_value = table_mock

    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, redis_client, sb, insert_mock


def test_get_history_401_without_auth(client):
    c, *_ = client
    res = c.get("/api/v1/history")
    assert res.status_code == 401


def test_get_history_403_on_free_plan(client):
    c, *_ = client
    res = c.get("/api/v1/history", headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 403


def test_post_history_403_on_free_plan(client):
    c, *_ = client
    body = {
        "query": "What is VAT?",
        "language": "ms",
        "domain": "tax",
        "response_summary": "VAT is a consumption tax.",
        "citations": [],
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header(sub="free-user", plan="free"))
    assert res.status_code == 403


def test_post_history_persists_redis_and_supabase(client):
    c, redis_client, sb, insert_mock = client
    stored = json.dumps(
        {
            "query": "What is VAT?",
            "language": "ms",
            "domain": "tax",
            "response_summary": "VAT is a consumption tax applied at each stage.",
            "citations": [{"url": "https://example.com"}],
        }
    )
    redis_client.lrange = AsyncMock(return_value=[stored])

    body = {
        "query": "What is VAT?",
        "language": "ms",
        "domain": "tax",
        "response_summary": "VAT is a consumption tax applied at each stage.",
        "citations": [{"url": "https://example.com"}],
    }
    res = c.post("/api/v1/history", json=body, headers=_auth_header())
    assert res.status_code == 201
    redis_client.pipeline.assert_called()
    pipe = redis_client.pipeline.return_value
    pipe.lpush.assert_called_once()
    pipe.ltrim.assert_called_once()
    pipe.execute.assert_called_once()
    sb.table.assert_called_with("user_sessions")
    insert_mock.execute.assert_called_once()


def test_history_authenticated_rate_limit_201st_returns_429(client):
    c, *_ = client
    headers = _auth_header(sub="hist-rate-user")
    for i in range(200):
        r = c.get("/api/v1/history", headers=headers)
        assert r.status_code == 200, r.text
    blocked = c.get("/api/v1/history", headers=headers)
    assert blocked.status_code == 429
    lowered = {k.lower(): v for k, v in blocked.headers.items()}
    assert "retry-after" in lowered
