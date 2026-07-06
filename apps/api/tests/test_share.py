import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


def _auth_header(sub: str = "share-user") -> dict[str, str]:
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

    def fake_from_url(*args, **kwargs):
        return redis_client

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[{"id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301"}])
    table_mock = MagicMock()
    table_mock.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    table_mock.insert.return_value = insert_mock

    sb = MagicMock()
    sb.table.return_value = table_mock

    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, sb, table_mock


def _body(**overrides):
    body = {
        "query": "What is the EPF withdrawal age?",
        "response_text": "You can withdraw EPF Account 2 savings at age 55.",
        "citations": [{"url": "https://www.kwsp.gov.my"}],
        "domain": "epf",
        "language": "en",
        "confidence": 0.87,
    }
    body.update(overrides)
    return body


def test_post_share_anonymous_allowed(client):
    c, sb, table_mock = client
    res = c.post("/api/v1/share", json=_body())
    assert res.status_code == 201, res.text
    assert res.json() == {"id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301"}
    sb.table.assert_called_with("shared_answers")
    inserted_row = table_mock.insert.call_args[0][0]
    assert inserted_row["user_id"] is None
    assert inserted_row["query"] == _body()["query"]


def test_post_share_authenticated_records_user_id(client):
    c, sb, table_mock = client
    res = c.post("/api/v1/share", json=_body(), headers=_auth_header(sub="share-user"))
    assert res.status_code == 201, res.text
    inserted_row = table_mock.insert.call_args[0][0]
    assert inserted_row["user_id"] == "share-user"


def test_post_share_rejects_oversized_response(client):
    c, *_ = client
    res = c.post("/api/v1/share", json=_body(response_text="y" * 20001))
    assert res.status_code == 422


def test_post_share_rejects_too_many_citations(client):
    c, *_ = client
    res = c.post("/api/v1/share", json=_body(citations=[{"url": "https://x.com"}] * 101))
    assert res.status_code == 422


def test_post_share_503_when_supabase_unavailable(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.post("/api/v1/share", json=_body())
    assert res.status_code == 503


def test_get_share_returns_full_answer(client):
    c, sb, table_mock = client
    share_id = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    table_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": share_id,
                "query": "What is the EPF withdrawal age?",
                "response_text": "You can withdraw EPF Account 2 savings at age 55.",
                "citations": [],
                "domain": "epf",
                "language": "en",
                "confidence": 0.87,
            }
        ]
    )
    res = c.get(f"/api/v1/share/{share_id}")
    assert res.status_code == 200, res.text
    assert res.json()["query"] == "What is the EPF withdrawal age?"


def test_get_share_404_when_not_found(client):
    c, *_ = client
    res = c.get("/api/v1/share/3f2504e0-4f89-11d3-9a0c-0305e82c3301")
    assert res.status_code == 404


def test_get_share_404_on_malformed_id(client):
    c, *_ = client
    res = c.get("/api/v1/share/not-a-uuid")
    assert res.status_code == 404


def test_get_share_no_auth_required(client):
    c, sb, table_mock = client
    share_id = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    table_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": share_id, "query": "q", "response_text": "a", "citations": [], "domain": "general", "language": "en", "confidence": None}]
    )
    res = c.get(f"/api/v1/share/{share_id}")  # no Authorization header
    assert res.status_code == 200, res.text


def test_post_share_rate_limit_31st_anonymous_returns_429(client):
    c, *_ = client
    for i in range(30):
        r = c.post("/api/v1/share", json=_body(query=f"q{i}"))
        assert r.status_code == 201, r.text
    blocked = c.post("/api/v1/share", json=_body(query="q-blocked"))
    assert blocked.status_code == 429
