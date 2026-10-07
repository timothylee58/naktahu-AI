"""Regression tests for the API-key rate limiter's Redis-outage behaviour.

Before this, `_apply_rate_limit` left `used` at 0 whenever Redis was absent,
and raised outright when a configured Redis client threw mid-call. Both paths
meant a Redis outage removed the cap entirely — metered LLM spend (ILMU /
Anthropic) went uncapped for the duration, which is the precise failure the
limiter exists to prevent.

The fix counts in-process instead. That is per-replica and therefore
imprecise, so these tests pin the property that actually matters: an outage
must still produce a 429 at the limit, rather than unlimited passage.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from middleware.api_key_rate_limit import (
    _apply_rate_limit,
    reset_fallback_counts_for_tests,
)
from services.api_key_service import ApiKeyContext


@pytest.fixture(autouse=True)
def _reset_fallback():
    reset_fallback_counts_for_tests()
    yield
    reset_fallback_counts_for_tests()


def _ctx(key_id: str = "key-1", limit: int = 3) -> ApiKeyContext:
    return ApiKeyContext(
        key_id=key_id,
        user_id="u1",
        plan="pro",
        calls_used=0,
        calls_limit=1000,
        rate_limit_per_min=limit,
        domain_whitelist=[],
        white_label=False,
        widget=False,
        sse=False,
        multi=False,
    )


def _request(redis_client) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(redis=redis_client)),
        state=SimpleNamespace(),
    )


class _ExplodingRedis:
    """Mimics a configured-but-unreachable Redis (connection reset/timeout)."""

    async def incr(self, _key: str) -> int:
        raise ConnectionError("connection reset by peer")

    async def expire(self, _key: str, _ttl: int) -> None:  # pragma: no cover
        raise ConnectionError("connection reset by peer")


@pytest.mark.asyncio
async def test_no_redis_client_still_enforces_limit() -> None:
    """app.state.redis is None (degraded boot) — must still cap at the limit."""
    ctx = _ctx(limit=3)
    for _ in range(3):
        await _apply_rate_limit(_request(None), ctx)

    with pytest.raises(HTTPException) as exc:
        await _apply_rate_limit(_request(None), ctx)
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_redis_raising_falls_back_instead_of_500() -> None:
    """A throwing Redis client used to propagate out as a 500 (no limiting at
    all). It must degrade to the in-process counter and still 429."""
    ctx = _ctx(limit=2)
    redis = _ExplodingRedis()

    for _ in range(2):
        await _apply_rate_limit(_request(redis), ctx)

    with pytest.raises(HTTPException) as exc:
        await _apply_rate_limit(_request(redis), ctx)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


@pytest.mark.asyncio
async def test_fallback_counts_are_isolated_per_key() -> None:
    """One key exhausting its budget during an outage must not throttle another."""
    a, b = _ctx("key-a", limit=1), _ctx("key-b", limit=1)

    await _apply_rate_limit(_request(None), a)
    with pytest.raises(HTTPException):
        await _apply_rate_limit(_request(None), a)

    # key-b is untouched by key-a's exhaustion.
    await _apply_rate_limit(_request(None), b)


@pytest.mark.asyncio
async def test_rate_limit_headers_present_on_fallback_path() -> None:
    """Clients rely on X-RateLimit-* to self-throttle; an outage shouldn't
    silently drop the headers and leave them flying blind."""
    ctx = _ctx(limit=5)
    request = _request(None)
    await _apply_rate_limit(request, ctx)

    headers = request.state.rate_limit_headers
    assert headers["X-RateLimit-Limit"] == "5"
    assert headers["X-RateLimit-Remaining"] == "4"
    assert "X-RateLimit-Reset" in headers
