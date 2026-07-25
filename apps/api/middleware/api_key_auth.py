"""API key authentication via X-NakTahu-Key header (separate from JWT)."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status

from services.api_key_service import ApiKeyContext, origin_allowed, validate_api_key

API_KEY_HEADER = "X-NakTahu-Key"


async def get_api_key_context(request: Request) -> ApiKeyContext:
    raw_key = request.headers.get(API_KEY_HEADER)
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    supabase = getattr(request.app.state, "supabase", None)
    redis_client = getattr(request.app.state, "redis", None)
    ctx = await validate_api_key(supabase, redis_client, raw_key)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if ctx.widget and ctx.domain_whitelist and not origin_allowed(ctx, origin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed for this API key",
        )

    request.state.api_key_context = ctx
    request.state.api_key_id = ctx.key_id
    return ctx


async def get_optional_api_key_context(request: Request) -> Optional[ApiKeyContext]:
    if not request.headers.get(API_KEY_HEADER):
        return None
    return await get_api_key_context(request)


def require_api_feature(feature: str):
    """Dependency factory: growth+ for sse/multi, white_label plan for branding."""

    async def _check(ctx: Annotated[ApiKeyContext, Depends(get_api_key_context)]) -> ApiKeyContext:
        allowed = getattr(ctx, feature, False)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API plan does not include {feature.replace('_', ' ')}",
            )
        return ctx

    return _check
