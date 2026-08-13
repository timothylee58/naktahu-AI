"""Per-API-key rate limiting with X-RateLimit-* headers."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status

from middleware.api_key_auth import get_api_key_context, require_api_feature
from services.api_key_service import ApiKeyContext

log = structlog.get_logger(__name__)

# ── In-process fallback counter ─────────────────────────────────────────────
# Used ONLY when Redis is unreachable. This used to fail OPEN: a Redis
# outage left `used` at 0 forever, so every API key became effectively
# unlimited and metered LLM spend (ILMU/Anthropic) was uncapped for the
# duration — the exact failure mode rate limiting exists to prevent.
#
# This is deliberately per-process and therefore imprecise: with N API
# replicas a key can burst up to N x limit during an outage. That is an
# accepted tradeoff — bounding the blast radius to a known multiple beats
# both unbounded spend (fail-open) and a hard outage (fail-closed 503).
# Redis remains the source of truth whenever it is reachable.
_fallback_counts: dict[tuple[str, int], int] = defaultdict(int)
_fallback_lock = threading.Lock()


def _fallback_incr(key_id: str, minute_bucket: int) -> int:
    """Increment and return the in-process counter for this key+minute.

    Prunes buckets older than the current minute on each call so the dict
    can't grow without bound across a long outage.
    """
    with _fallback_lock:
        for stale in [k for k in _fallback_counts if k[1] < minute_bucket]:
            del _fallback_counts[stale]
        bucket = (key_id, minute_bucket)
        _fallback_counts[bucket] += 1
        return _fallback_counts[bucket]


def reset_fallback_counts_for_tests() -> None:
    with _fallback_lock:
        _fallback_counts.clear()


async def enforce_api_key_rate_limit(
    request: Request,
    ctx: Annotated[ApiKeyContext, Depends(get_api_key_context)],
) -> ApiKeyContext:
    """Redis per-minute bucket with X-RateLimit-* headers."""
    await _apply_rate_limit(request, ctx)
    return ctx


async def enforce_sse_rate_limit(
    request: Request,
    ctx: Annotated[ApiKeyContext, Depends(require_api_feature("sse"))],
) -> ApiKeyContext:
    await _apply_rate_limit(request, ctx)
    return ctx


async def enforce_multi_rate_limit(
    request: Request,
    ctx: Annotated[ApiKeyContext, Depends(require_api_feature("multi"))],
) -> ApiKeyContext:
    await _apply_rate_limit(request, ctx)
    return ctx


async def _apply_rate_limit(request: Request, ctx: ApiKeyContext) -> None:
    redis_client = getattr(request.app.state, "redis", None)
    limit = ctx.rate_limit_per_min
    minute_bucket = int(time.time()) // 60
    reset_at = (minute_bucket + 1) * 60

    # Redis is the source of truth; the in-process counter is the fallback
    # for BOTH "no client configured" and "client configured but the call
    # failed" — the latter (connection reset / timeout mid-outage) is the
    # common real-world case and previously raised straight past the limit
    # check, which FastAPI turned into a 500 rather than any limiting.
    if redis_client is None:
        used = _fallback_incr(ctx.key_id, minute_bucket)
    else:
        rk = f"api_key:rpm:{ctx.key_id}:{minute_bucket}"
        try:
            used = int(await redis_client.incr(rk))
            if used == 1:
                await redis_client.expire(rk, 120)
        except Exception as exc:  # redis down / connection reset / timeout
            used = _fallback_incr(ctx.key_id, minute_bucket)
            log.warning(
                "api_key_rate_limit_redis_unavailable",
                error=str(exc),
                key_id=ctx.key_id,
                fallback_used=used,
                detail="counting in-process; limit is per-replica until Redis recovers",
            )

    remaining = max(0, limit - used)
    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_at),
    }
    request.state.rate_limit_headers = headers

    if used > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={**headers, "Retry-After": str(reset_at - int(time.time()))},
        )
