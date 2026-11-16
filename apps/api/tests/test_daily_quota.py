"""Tests for daily query quota enforcement."""
from __future__ import annotations

import pytest

from services.daily_quota import (
    FREE_DAILY_LIMIT,
    check_and_increment_daily_quota,
    is_free_plan,
    refund_daily_quota,
)


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}
        self.ttl: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def decr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 1) - 1
        return self.store[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.ttl[key] = seconds

    async def get(self, key: str) -> str | None:
        v = self.store.get(key)
        return str(v) if v is not None else None


@pytest.mark.asyncio
async def test_free_plan_enforces_daily_limit() -> None:
    redis = FakeRedis()
    for i in range(FREE_DAILY_LIMIT):
        allowed, used, limit = await check_and_increment_daily_quota(
            redis, identifier="auth:user1", plan="free"
        )
        assert allowed is True
        assert used == i + 1
    allowed, used, limit = await check_and_increment_daily_quota(
        redis, identifier="auth:user1", plan="free"
    )
    assert allowed is False
    assert used == FREE_DAILY_LIMIT


@pytest.mark.asyncio
async def test_pro_plan_skips_quota() -> None:
    redis = FakeRedis()
    for _ in range(50):
        allowed, _, _ = await check_and_increment_daily_quota(
            redis, identifier="auth:pro-user", plan="pro"
        )
        assert allowed is True
    assert len(redis.store) == 0


def test_is_free_plan() -> None:
    assert is_free_plan("free") is True
    assert is_free_plan("pro") is False
    assert is_free_plan(None) is True


@pytest.mark.asyncio
async def test_refund_gives_back_one_unit() -> None:
    redis = FakeRedis()
    await check_and_increment_daily_quota(redis, identifier="auth:u", plan="free")
    await check_and_increment_daily_quota(redis, identifier="auth:u", plan="free")
    await refund_daily_quota(redis, identifier="auth:u", plan="free")
    _, used, _ = await check_and_increment_daily_quota(redis, identifier="auth:u", plan="free")
    assert used == 2


@pytest.mark.asyncio
async def test_refund_never_drops_below_zero() -> None:
    redis = FakeRedis()
    await refund_daily_quota(redis, identifier="auth:u", plan="free")
    assert list(redis.store.values()) == [0]


@pytest.mark.asyncio
async def test_refund_is_noop_for_paid_plans_and_missing_redis() -> None:
    redis = FakeRedis()
    await refund_daily_quota(redis, identifier="auth:pro", plan="pro")
    await refund_daily_quota(None, identifier="auth:u", plan="free")
    assert redis.store == {}


@pytest.mark.asyncio
async def test_refund_swallows_redis_errors() -> None:
    class BrokenRedis(FakeRedis):
        async def decr(self, key: str) -> int:
            raise ConnectionError("down")

    await refund_daily_quota(BrokenRedis(), identifier="auth:u", plan="free")
