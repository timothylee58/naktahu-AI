"""Tests for the domain/language-agnostic "seen" marker in
app/services/cache.py — the piece that makes router_node's speculative
query-embedding safe (see cache.has_query_been_seen's own docstring for
why an absent marker guarantees the real cache lookup will also miss)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services import cache as cache_svc


@pytest.mark.asyncio
async def test_mark_and_has_seen_round_trip():
    client = AsyncMock()
    client.setex = AsyncMock()
    client.exists = AsyncMock(return_value=1)

    with patch("app.services.cache._get_client", return_value=client):
        await cache_svc.mark_query_seen("How do I pay income tax?", ttl=3600)
        seen = await cache_svc.has_query_been_seen("How do I pay income tax?")

    assert seen is True
    client.setex.assert_awaited_once()
    args, _ = client.setex.await_args
    assert args[1] == 3600  # ttl passed through unchanged


@pytest.mark.asyncio
async def test_has_query_been_seen_ignores_case_and_whitespace():
    """Same normalization as rag_node's own _cache_key (lower + strip) —
    the marker must agree with what it's standing in for."""
    client = AsyncMock()
    client.exists = AsyncMock(return_value=0)

    with patch("app.services.cache._get_client", return_value=client):
        await cache_svc.has_query_been_seen("  How Do I Pay Income Tax?  ")

    key_arg = client.exists.await_args.args[0]

    client2 = AsyncMock()
    client2.exists = AsyncMock(return_value=0)
    with patch("app.services.cache._get_client", return_value=client2):
        await cache_svc.has_query_been_seen("how do i pay income tax?")

    key_arg2 = client2.exists.await_args.args[0]
    assert key_arg == key_arg2


@pytest.mark.asyncio
async def test_has_query_been_seen_fails_closed_on_redis_error():
    """A Redis error must degrade to False (don't speculate) — never True,
    which would skip a speculative embed that might actually be safe, but
    more importantly never silently crash the caller (router_node)."""
    client = AsyncMock()
    client.exists = AsyncMock(side_effect=RuntimeError("connection refused"))

    with patch("app.services.cache._get_client", return_value=client):
        seen = await cache_svc.has_query_been_seen("some query")

    assert seen is False


@pytest.mark.asyncio
async def test_mark_query_seen_swallows_redis_error():
    client = AsyncMock()
    client.setex = AsyncMock(side_effect=RuntimeError("connection refused"))

    with patch("app.services.cache._get_client", return_value=client):
        await cache_svc.mark_query_seen("some query")  # must not raise
