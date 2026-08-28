import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


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
        "name": "Jane Tan",
        "company": "Tan Trading Sdn Bhd",
        "contact_email": "jane@example.com",
        "message": "Interested in managed grant + compliance service.",
        "referral_source": "acme-secretarial",
    }
    body.update(overrides)
    return body


def test_post_lead_happy_path(client):
    c, sb, table_mock = client
    res = c.post("/api/v1/leads", json=_body())
    assert res.status_code == 201, res.text
    assert res.json() == {"id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301"}
    sb.table.assert_called_with("managed_leads")
    inserted = table_mock.insert.call_args[0][0]
    assert inserted["name"] == "Jane Tan"
    assert inserted["referral_source"] == "acme-secretarial"


def test_post_lead_anonymous_no_auth_required(client):
    """A prospective managed-service client has no NakTahu account yet —
    this endpoint must work with zero auth headers, matching the
    anonymous-friendly precedent in routers/parliament.py."""
    c, _sb, _table_mock = client
    res = c.post("/api/v1/leads", json=_body())
    assert res.status_code == 201


def test_post_lead_phone_only_is_accepted(client):
    c, _sb, _table_mock = client
    res = c.post("/api/v1/leads", json=_body(contact_email=None, contact_phone="+60123456789"))
    assert res.status_code == 201, res.text


def test_post_lead_requires_at_least_one_contact_method(client):
    c, _sb, _table_mock = client
    res = c.post("/api/v1/leads", json=_body(contact_email=None))
    assert res.status_code == 422


def test_post_lead_rejects_malformed_email(client):
    c, _sb, _table_mock = client
    res = c.post("/api/v1/leads", json=_body(contact_email="not-an-email"))
    assert res.status_code == 422


def test_post_lead_rejects_malformed_phone(client):
    c, _sb, _table_mock = client
    res = c.post("/api/v1/leads", json=_body(contact_email=None, contact_phone="call me maybe"))
    assert res.status_code == 422


def test_post_lead_rejects_oversized_name(client):
    c, _sb, _table_mock = client
    res = c.post("/api/v1/leads", json=_body(name="x" * 201))
    assert res.status_code == 422


def test_post_lead_rejects_missing_name(client):
    c, _sb, _table_mock = client
    body = _body()
    del body["name"]
    res = c.post("/api/v1/leads", json=body)
    assert res.status_code == 422


def test_post_lead_works_without_referral_source(client):
    c, _sb, table_mock = client
    res = c.post("/api/v1/leads", json=_body(referral_source=None))
    assert res.status_code == 201, res.text
    inserted = table_mock.insert.call_args[0][0]
    assert inserted["referral_source"] is None


def test_post_lead_degraded_mode_returns_503(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)
    monkeypatch.setattr(api_main, "create_client", lambda url, key: None)

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        res = c.post("/api/v1/leads", json=_body())
    assert res.status_code == 503


def test_post_lead_rate_limit_boundary(client):
    """5/minute per IP — the 6th request in a window must 429 with
    Retry-After."""
    c, _sb, _table_mock = client
    for _ in range(5):
        res = c.post("/api/v1/leads", json=_body())
        assert res.status_code == 201, res.text
    res = c.post("/api/v1/leads", json=_body())
    assert res.status_code == 429
    assert "Retry-After" in res.headers
