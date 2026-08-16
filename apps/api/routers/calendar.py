"""Deadline Monitor calendar sync — connect/callback/status/disconnect.

See services/calendar_sync.py's module docstring for the manual OAuth app
registration steps this router depends on, and the write-only-scope
rationale ("two-way sync" means NakTahu pushes events, never reads the
user's calendar).
"""
from __future__ import annotations

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user
from services.calendar_sync import (
    CalendarConfigMissing,
    build_authorize_url,
    consume_oauth_state,
    create_oauth_state,
    disconnect,
    exchange_code_for_tokens,
)
from app.services.token_encryption import TokenEncryptionUnavailable, encrypt_token
from core.config import settings

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])

Provider = Literal["google", "microsoft"]


class ConnectResponse(BaseModel):
    authorize_url: str


class ConnectionStatus(BaseModel):
    provider: Provider
    connected: bool
    last_synced_at: str | None = None
    last_error: str | None = None


@router.get("/connect/{provider}", response_model=ConnectResponse)
@apply_query_rate_limit()
async def get_connect_url(
    provider: Provider,
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.redis:
        raise HTTPException(status_code=503, detail="Calendar sync is temporarily unavailable")
    try:
        state = await create_oauth_state(request.app.state.redis, user.user_id)
        authorize_url = build_authorize_url(provider, state)
    except CalendarConfigMissing:
        raise HTTPException(status_code=503, detail=f"{provider} calendar sync is not configured yet")
    return ConnectResponse(authorize_url=authorize_url)


@router.get("/callback/{provider}", response_model=None)
async def oauth_callback(
    provider: Provider,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Browser redirect target from the provider — no Authorization header
    available here (per Trap #2, this endpoint is intentionally NOT rate
    limited with the slowapi decorator since it never carries an
    authenticated user or a `response: Response` param would otherwise be
    required for nothing). `state` (not a bearer token) identifies the user;
    see create_oauth_state/consume_oauth_state.
    """
    frontend_deadline_page = f"{settings.frontend_url}/agents/deadline-monitor"

    if error or not code or not state:
        return RedirectResponse(f"{frontend_deadline_page}?calendar_error={provider}")

    if not request.app.state.supabase or not request.app.state.redis:
        return RedirectResponse(f"{frontend_deadline_page}?calendar_error={provider}")

    user_id = await consume_oauth_state(request.app.state.redis, state)
    if not user_id:
        # Expired (>10 min) or already-used state — a replayed/stale
        # callback URL, not a live connection attempt.
        return RedirectResponse(f"{frontend_deadline_page}?calendar_error={provider}")

    try:
        tokens = await exchange_code_for_tokens(provider, code)
        encrypted = encrypt_token(tokens["refresh_token"])
    except (CalendarConfigMissing, TokenEncryptionUnavailable) as exc:
        log.error("calendar_callback_config_error", provider=provider, error=str(exc))
        return RedirectResponse(f"{frontend_deadline_page}?calendar_error={provider}")
    except Exception as exc:  # noqa: BLE001 — provider-side failure must still redirect, not 500
        log.error("calendar_callback_token_exchange_failed", provider=provider, error=str(exc))
        return RedirectResponse(f"{frontend_deadline_page}?calendar_error={provider}")

    request.app.state.supabase.table("calendar_connections").upsert(
        {
            "user_id": user_id,
            "provider": provider,
            "encrypted_refresh_token": encrypted,
            "scope": tokens["scope"],
            "last_error": None,
        },
        on_conflict="user_id,provider",
    ).execute()

    return RedirectResponse(f"{frontend_deadline_page}?calendar_connected={provider}")


@router.get("/status", response_model=list[ConnectionStatus])
@apply_query_rate_limit()
async def get_status(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Calendar sync is temporarily unavailable")

    rows = (
        request.app.state.supabase.table("calendar_connections")
        .select("provider,last_synced_at,last_error")
        .eq("user_id", user.user_id)
        .execute()
    )
    by_provider = {r["provider"]: r for r in (rows.data or [])}

    return [
        ConnectionStatus(
            provider=p,
            connected=p in by_provider,
            last_synced_at=by_provider.get(p, {}).get("last_synced_at"),
            last_error=by_provider.get(p, {}).get("last_error"),
        )
        for p in ("google", "microsoft")
    ]


@router.delete("/{provider}", status_code=204, response_model=None)
@apply_query_rate_limit()
async def delete_connection(
    provider: Provider,
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Calendar sync is temporarily unavailable")
    await disconnect(request.app.state.supabase, user.user_id, provider)
