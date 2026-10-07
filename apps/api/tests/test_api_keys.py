"""Tests for Developer API keys and public Knowledge API."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.config import settings
from services.api_key_service import (
    API_KEY_RAW_PREFIX,
    generate_api_key,
    hash_api_key,
)


def _auth_header(sub: str = "dev-user-1") -> dict[str, str]:
    token = jwt.encode(
        {"sub": sub, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
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
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    with TestClient(app) as c:
        yield c, sb, redis_client


def test_generate_api_key_format():
    raw, key_hash, prefix = generate_api_key()
    assert raw.startswith(API_KEY_RAW_PREFIX)
    assert key_hash == hash_api_key(raw)
    assert prefix == raw[:16]


def test_public_query_missing_key_returns_401(client):
    c, _, _ = client
    res = c.post("/api/v1/public/query", json={"query": "EPF withdrawal rules?"})
    assert res.status_code == 401


def test_public_query_invalid_key_returns_401(client):
    c, sb, _ = client
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    res = c.post(
        "/api/v1/public/query",
        json={"query": "EPF withdrawal rules?"},
        headers={"X-NakTahu-Key": f"{API_KEY_RAW_PREFIX}invalid"},
    )
    assert res.status_code == 401


def test_public_query_valid_key_returns_json(client):
    c, sb, redis = client
    raw, key_hash, _ = generate_api_key()
    key_id = "key-uuid-1"
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": key_id,
                "user_id": "user-1",
                "key_hash": key_hash,
                "key_prefix": raw[:16],
                "plan": "starter",
                "calls_used": 0,
                "calls_limit": 5500,
                "rate_limit_per_min": 10,
                "domain_whitelist": [],
                "active": True,
            }
        ]
    )
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

    pipeline_result = {
        "tokens": ["Jawapan", " ringkas."],
        "final_state": {
            "citations": [{"title": "EPF", "ministry": "KWSP", "url": "https://www.kwsp.gov.my", "confidence": 0.9}],
            "confidence_score": 0.88,
            "domain": "epf",
            "language": "bm",
        },
        "metrics": {"latency_ms": 1200},
    }

    with patch("routers.api_v1_public._run_pipeline", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = pipeline_result
        res = c.post(
            "/api/v1/public/query",
            json={"query": "Cara keluarkan EPF?", "language": "bm"},
            headers={"X-NakTahu-Key": raw},
        )

    assert res.status_code == 200
    body = res.json()
    assert "answer" in body
    assert body["domain"] == "epf"
    assert body["confidence"] == 0.88
    assert "X-RateLimit-Limit" in res.headers


def test_public_query_stream_returns_sse_events(client):
    """Public Knowledge API's own SSE endpoint (/query/stream) — no
    existing coverage before this. Mocks _stream_pipeline (not
    _run_pipeline) since that's what actually feeds this endpoint's token
    events post-fix — see app/routers/query.py's module for why
    /query/stream now streams tokens as they arrive instead of buffering
    the whole answer first."""
    c, sb, redis = client
    raw, key_hash, _ = generate_api_key()
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "key-uuid-2",
                "user_id": "user-1",
                "key_hash": key_hash,
                "key_prefix": raw[:16],
                "plan": "growth",  # SSE requires the sse feature flag — see API_PLAN_DEFAULTS
                "calls_used": 0,
                "calls_limit": 50000,
                "rate_limit_per_min": 60,
                "domain_whitelist": [],
                "active": True,
            }
        ]
    )
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

    async def _fake_stream(query, session_id, user_id, domain=None):
        yield "token", "Jawapan"
        yield "token", " ringkas."
        yield "result", {
            "tokens": ["Jawapan", " ringkas."],
            "final_state": {
                "citations": [{"title": "EPF", "ministry": "KWSP", "url": "https://www.kwsp.gov.my", "confidence": 0.9}],
                "confidence_score": 0.88,
                "domain": "epf",
                "language": "bm",
            },
            "metrics": {"latency_ms": 900},
        }

    with patch("routers.api_v1_public._stream_pipeline", new=_fake_stream):
        res = c.post(
            "/api/v1/public/query/stream",
            json={"query": "Cara keluarkan EPF?", "language": "bm"},
            headers={"X-NakTahu-Key": raw},
        )

    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    assert "event: token" in res.text
    assert "event: citation" in res.text
    assert "event: done" in res.text


def test_developer_create_key_requires_auth(client):
    c, _, _ = client
    res = c.post("/api/v1/developer/keys", json={"plan": "starter"})
    assert res.status_code == 401


def test_public_openapi_json(client):
    c, _, _ = client
    res = c.get("/api/v1/public/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert "/api/v1/public/query" in schema.get("paths", {})


def test_public_docs_html(client):
    c, _, _ = client
    res = c.get("/api/v1/public/docs")
    assert res.status_code == 200
    assert "swagger-ui" in res.text.lower()


def test_public_docs_is_branded_and_links_to_frontend_not_relative(client):
    """The docs page is served from the API's own origin (Railway), not
    the web app's (Netlify) — a relative /developer link would 404 here,
    so the branded header must resolve against settings.frontend_url and
    never leak the __FRONTEND__ template placeholder into the response."""
    from core.config import settings

    c, _, _ = client
    res = c.get("/api/v1/public/docs")

    assert "NakTahu Knowledge API" in res.text
    assert "__FRONTEND__" not in res.text
    assert f'{settings.frontend_url.rstrip("/")}/developer' in res.text
