"""Daily query quota for free-tier users (25/day by default).

Paid plans (student, pro, business) are exempt. Anonymous users are keyed
by IP; authenticated free users by user_id. Counter resets at UTC midnight
via Redis TTL.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

import structlog

log = structlog.get_logger(__name__)

FREE_DAILY_LIMIT = int(os.environ.get("FREE_DAILY_QUERY_LIMIT", "25"))
_QUOTA_TTL_SECONDS = 86_400  # 24 h rolling window keyed by calendar day


def _quota_key(identifier: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"quota:daily:{identifier}:{today}"


def is_free_plan(plan: str | None) -> bool:
    return (plan or "free") == "free"


async def check_and_increment_daily_quota(
    redis_client,
    *,
    identifier: str,
    plan: str | None,
) -> tuple[bool, int, int]:
    """Return (allowed, used_count, limit). Increments on allowed request."""
    if not is_free_plan(plan):
        return True, 0, FREE_DAILY_LIMIT

    if redis_client is None:
        log.warning("daily_quota_redis_unavailable")
        return True, 0, FREE_DAILY_LIMIT

    key = _quota_key(identifier)
    used = await redis_client.incr(key)
    if used == 1:
        await redis_client.expire(key, _QUOTA_TTL_SECONDS)

    if used > FREE_DAILY_LIMIT:
        await redis_client.decr(key)
        return False, FREE_DAILY_LIMIT, FREE_DAILY_LIMIT

    return True, used, FREE_DAILY_LIMIT


async def get_daily_usage(redis_client, identifier: str) -> int:
    if redis_client is None:
        return 0
    raw = await redis_client.get(_quota_key(identifier))
    return int(raw) if raw else 0
