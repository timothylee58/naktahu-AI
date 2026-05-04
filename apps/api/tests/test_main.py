"""Tests for FastAPI application lifespan startup error handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import main as api_main
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


@pytest.fixture(autouse=True)
def reset_limiters():
    anonymous_limiter.reset()
    authenticated_limiter.reset()
    yield
    anonymous_limiter.reset()
    authenticated_limiter.reset()


def test_lifespan_redis_ping_failure_raises(monkeypatch):
    failing_redis = AsyncMock()
    failing_redis.ping = AsyncMock(side_effect=Exception("Redis unavailable"))
    failing_redis.aclose = AsyncMock(return_value=None)

    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **kw: failing_redis)

    with pytest.raises(Exception, match="Redis unavailable"):
        with TestClient(api_main.app):
            pass  # pragma: no cover


def test_lifespan_supabase_failure_raises(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)
    monkeypatch.setattr(api_main.redis_ai, "from_url", lambda *a, **kw: redis_client)

    def failing_create_client(*args, **kwargs):
        raise Exception("Supabase unavailable")

    monkeypatch.setattr(api_main, "create_client", failing_create_client)

    with pytest.raises(Exception, match="Supabase unavailable"):
        with TestClient(api_main.app):
            pass  # pragma: no cover
