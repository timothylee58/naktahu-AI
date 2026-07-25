"""Tests for middleware.security_headers — baseline defensive response headers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import main as api_main
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **k: redis_client)
    monkeypatch.setattr(api_main, "create_client", lambda url, key: MagicMock())

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c


def test_security_headers_present_on_health_endpoint(client):
    res = client.get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in res.headers["Permissions-Policy"]


def test_security_headers_present_on_404(client):
    """Headers must apply even to error responses, not just successful ones."""
    res = client.get("/api/v1/this-route-does-not-exist")
    assert res.status_code == 404
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
