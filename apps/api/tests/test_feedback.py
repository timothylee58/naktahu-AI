import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


def _auth_header(sub: str = "feedback-user") -> dict[str, str]:
    tok = jwt.encode(
        {
            "sub": sub,
            "aud": settings.supabase_jwt_aud,
            "exp": int(time.time()) + 3600,
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
        yield c, sb, insert_mock


def _body(**overrides):
    body = {
        "session_id": "anon-123",
        "query": "What is the EPF withdrawal age?",
        "response_summary": "You can withdraw EPF Account 2 savings at age 55.",
        "citations": [{"url": "https://www.kwsp.gov.my"}],
        "domain": "epf",
        "language": "en",
        "rating": 1,
    }
    body.update(overrides)
    return body


def test_post_feedback_anonymous_allowed(client):
    c, sb, insert_mock = client
    res = c.post("/api/v1/feedback", json=_body())
    assert res.status_code == 201, res.text
    assert res.json() == {"status": "recorded"}
    sb.table.assert_called_with("feedback")
    insert_mock.execute.assert_called_once()
    inserted_row = sb.table.return_value.insert.call_args[0][0]
    assert inserted_row["user_id"] is None
    assert inserted_row["rating"] == 1


def test_post_feedback_authenticated_records_user_id(client):
    c, sb, insert_mock = client
    res = c.post("/api/v1/feedback", json=_body(rating=-1), headers=_auth_header(sub="feedback-user"))
    assert res.status_code == 201, res.text
    inserted_row = sb.table.return_value.insert.call_args[0][0]
    assert inserted_row["user_id"] == "feedback-user"
    assert inserted_row["rating"] == -1


def test_post_feedback_rejects_invalid_rating(client):
    c, *_ = client
    res = c.post("/api/v1/feedback", json=_body(rating=0))
    assert res.status_code == 422


def test_post_feedback_rejects_response_summary_over_max_length(client):
    c, *_ = client
    res = c.post("/api/v1/feedback", json=_body(response_summary="y" * 2001))
    assert res.status_code == 422


def test_post_feedback_rate_limit_31st_anonymous_returns_429(client):
    c, *_ = client
    for i in range(30):
        r = c.post("/api/v1/feedback", json=_body(query=f"q{i}"))
        assert r.status_code == 201, r.text
    blocked = c.post("/api/v1/feedback", json=_body(query="q-blocked"))
    assert blocked.status_code == 429


def test_post_feedback_returns_503_when_supabase_unavailable(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.post("/api/v1/feedback", json=_body())
    assert res.status_code == 503


def test_post_feedback_rejects_unknown_domain(client):
    c, *_ = client
    res = c.post("/api/v1/feedback", json=_body(domain="not-a-real-domain"))
    assert res.status_code == 422


def test_post_feedback_rejects_unknown_language(client):
    c, *_ = client
    res = c.post("/api/v1/feedback", json=_body(language="klingon"))
    assert res.status_code == 422


def test_post_feedback_rejects_oversized_citations_list(client):
    c, *_ = client
    res = c.post("/api/v1/feedback", json=_body(citations=[{"url": "https://x.com"}] * 101))
    assert res.status_code == 422
