"""Per-API-key rate limiting with X-RateLimit-* headers."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from middleware.api_key_auth import get_api_key_context, require_api_feature
from services.api_key_service import ApiKeyContext


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

    used = 0
    if redis_client is not None:
        rk = f"api_key:rpm:{ctx.key_id}:{minute_bucket}"
        used = int(await redis_client.incr(rk))
        if used == 1:
            await redis_client.expire(rk, 120)

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
