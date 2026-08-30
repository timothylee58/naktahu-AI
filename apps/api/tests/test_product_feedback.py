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

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(
        data=[{
            "id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
            "category": "bug",
            "title": "Search box freezes",
            "status": "new",
            "created_at": "2026-08-30T00:00:00Z",
        }]
    )
    select_mock = MagicMock()
    select_mock.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    table_mock.select.return_value = select_mock

    sb = MagicMock()
    sb.table.return_value = table_mock
    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, sb, table_mock


def _body(**overrides):
    body = {
        "category": "bug",
        "title": "Search box freezes",
        "description": "Typing quickly in the landing search box sometimes freezes the page.",
    }
    body.update(overrides)
    return body


def test_post_product_feedback_happy_path(client):
    c, sb, table_mock = client
    res = c.post("/api/v1/product-feedback", json=_body(), headers=_auth_header())
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["category"] == "bug"
    assert data["status"] == "new"
    sb.table.assert_called_with("product_feedback")
    inserted = table_mock.insert.call_args[0][0]
    assert inserted["title"] == "Search box freezes"
    assert inserted["user_id"] == "feedback-user"


def test_post_product_feedback_requires_auth(client):
    c, _sb, _table_mock = client
    res = c.post("/api/v1/product-feedback", json=_body())
    assert res.status_code == 401


def test_post_product_feedback_accepts_feature_request_and_general(client):
    c, _sb, _table_mock = client
    for category in ("feature_request", "general"):
        res = c.post("/api/v1/product-feedback", json=_body(category=category), headers=_auth_header())
        assert res.status_code == 201, res.text


def test_post_product_feedback_rejects_invalid_category(client):
    c, _sb, _table_mock = client
    res = c.post("/api/v1/product-feedback", json=_body(category="not-a-real-category"), headers=_auth_header())
    assert res.status_code == 422


def test_post_product_feedback_rejects_missing_title(client):
    c, _sb, _table_mock = client
    body = _body()
    del body["title"]
    res = c.post("/api/v1/product-feedback", json=body, headers=_auth_header())
    assert res.status_code == 422


def test_post_product_feedback_rejects_oversized_description(client):
    c, _sb, _table_mock = client
    res = c.post("/api/v1/product-feedback", json=_body(description="x" * 2001), headers=_auth_header())
    assert res.status_code == 422


def test_post_product_feedback_strips_whitespace(client):
    c, _sb, table_mock = client
    res = c.post(
        "/api/v1/product-feedback",
        json=_body(title="  Search box freezes  ", description="  detail  "),
        headers=_auth_header(),
    )
    assert res.status_code == 201, res.text
    inserted = table_mock.insert.call_args[0][0]
    assert inserted["title"] == "Search box freezes"
    assert inserted["description"] == "detail"


def test_post_product_feedback_degraded_mode_returns_503(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)
    monkeypatch.setattr(api_main, "create_client", lambda url, key: None)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        res = c.post("/api/v1/product-feedback", json=_body(), headers=_auth_header())
    assert res.status_code == 503


def test_get_own_product_feedback_happy_path(client):
    c, sb, table_mock = client
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{
            "id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
            "category": "bug",
            "title": "Search box freezes",
            "description": "detail",
            "status": "new",
            "created_at": "2026-08-30T00:00:00Z",
        }]
    )
    res = c.get("/api/v1/product-feedback", headers=_auth_header())
    assert res.status_code == 200, res.text
    assert len(res.json()["results"]) == 1
    sb.table.assert_called_with("product_feedback")


def test_get_own_product_feedback_requires_auth(client):
    c, _sb, _table_mock = client
    res = c.get("/api/v1/product-feedback")
    assert res.status_code == 401


def test_get_own_product_feedback_degraded_mode_returns_503(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)
    monkeypatch.setattr(api_main, "create_client", lambda url, key: None)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        res = c.get("/api/v1/product-feedback", headers=_auth_header())
    assert res.status_code == 503
