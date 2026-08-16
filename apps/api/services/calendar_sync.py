"""Two-way(-push) OAuth calendar sync for Deadline Monitor.

"Two-way" means NakTahu creates/updates/deletes calendar EVENTS on the
user's behalf for their subscribed deadlines — it does NOT read the user's
existing calendar. Google's `calendar.events` scope is write-capable
without full calendar read; Microsoft Graph has no equivalent write-only
scope, so `Calendars.ReadWrite` is used there even though this app never
reads — stated honestly rather than claimed narrower than it is.

## Manual setup this code depends on (cannot be done from this sandbox)

**Google Cloud Console** (console.cloud.google.com):
1. Create/select a project -> APIs & Services -> enable "Google Calendar API".
2. APIs & Services -> Credentials -> Create OAuth client ID -> Web application.
3. Authorized redirect URI: `{PUBLIC_API_URL}/api/v1/calendar/callback/google`
   (e.g. `https://api.naktahu.ai/api/v1/calendar/callback/google`).
4. Copy the Client ID and Client Secret -> set as GOOGLE_CALENDAR_CLIENT_ID /
   GOOGLE_CALENDAR_CLIENT_SECRET.

**Microsoft Entra** (entra.microsoft.com):
1. App registrations -> New registration. Redirect URI (Web platform):
   `{PUBLIC_API_URL}/api/v1/calendar/callback/microsoft`.
2. API permissions -> Microsoft Graph -> Delegated -> add `Calendars.ReadWrite`
   and `offline_access` (needed for refresh tokens).
3. Certificates & secrets -> New client secret -> copy its VALUE (not the
   secret ID) -> set as MICROSOFT_CALENDAR_CLIENT_SECRET; the Application
   (client) ID from the Overview page -> MICROSOFT_CALENDAR_CLIENT_ID.

**Both**: generate an encryption key once with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
and set it as CALENDAR_TOKEN_ENCRYPTION_KEY.

Until all of these are set, `/api/v1/calendar/*` degrades to 503 (Trap #4) —
never crashes, never silently no-ops as if connected.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import httpx
import structlog

from app.services.token_encryption import decrypt_token
from core.config import settings

log = structlog.get_logger(__name__)

Provider = Literal["google", "microsoft"]

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
_GOOGLE_SCOPE = "https://www.googleapis.com/auth/calendar.events"

_MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_MS_GRAPH_API = "https://graph.microsoft.com/v1.0"
_MS_SCOPE = "offline_access Calendars.ReadWrite"

# OAuth state tokens live in Redis for 10 minutes — long enough for a real
# consent flow, short enough that a leaked/logged state can't be replayed
# later. Maps state -> user_id so the callback (which gets no Authorization
# header — it's a browser redirect from the provider) knows who connected.
_STATE_TTL_SECONDS = 600
_STATE_KEY_PREFIX = "calendar_oauth_state:"


class CalendarConfigMissing(RuntimeError):
    """A provider's OAuth client id/secret isn't configured."""


def _client_credentials(provider: Provider) -> tuple[str, str]:
    if provider == "google":
        client_id, client_secret = settings.google_calendar_client_id, settings.google_calendar_client_secret
    else:
        client_id, client_secret = settings.microsoft_calendar_client_id, settings.microsoft_calendar_client_secret
    if not client_id or not client_secret:
        raise CalendarConfigMissing(f"{provider} OAuth client id/secret not configured")
    return client_id, client_secret


def _redirect_uri(provider: Provider) -> str:
    return f"{settings.public_api_url}/api/v1/calendar/callback/{provider}"


async def create_oauth_state(redis_client, user_id: str) -> str:
    state = secrets.token_urlsafe(32)
    await redis_client.setex(f"{_STATE_KEY_PREFIX}{state}", _STATE_TTL_SECONDS, user_id)
    return state


async def consume_oauth_state(redis_client, state: str) -> str | None:
    """One-time use — deletes the state on read so a replayed callback URL
    (e.g. from browser history) can't re-trigger token exchange."""
    key = f"{_STATE_KEY_PREFIX}{state}"
    user_id = await redis_client.get(key)
    if user_id is not None:
        await redis_client.delete(key)
    return user_id


def build_authorize_url(provider: Provider, state: str) -> str:
    client_id, _ = _client_credentials(provider)
    redirect_uri = _redirect_uri(provider)
    if provider == "google":
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _GOOGLE_SCOPE,
            "access_type": "offline",
            # Forces the consent screen (and therefore a refresh_token) even
            # for a user re-connecting after a prior disconnect — Google
            # otherwise only issues a refresh_token on a account's *first*
            # consent.
            "prompt": "consent",
            "state": state,
        }
        return f"{_GOOGLE_AUTH_URL}?{httpx.QueryParams(params)}"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "response_mode": "query",
        "scope": _MS_SCOPE,
        "state": state,
    }
    return f"{_MS_AUTH_URL}?{httpx.QueryParams(params)}"


async def exchange_code_for_tokens(provider: Provider, code: str) -> dict:
    """Returns {"refresh_token": str, "access_token": str, "scope": str}."""
    client_id, client_secret = _client_credentials(provider)
    redirect_uri = _redirect_uri(provider)
    token_url = _GOOGLE_TOKEN_URL if provider == "google" else _MS_TOKEN_URL
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_url, data=data)
        resp.raise_for_status()
        payload = resp.json()

    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        # Google omits refresh_token on a re-consent it doesn't recognize as
        # "first time" despite prompt=consent in rare cases; Microsoft omits
        # it if offline_access wasn't actually granted. Either way, a
        # connection without a refresh token is useless for a background
        # sync job — fail loudly instead of silently storing an
        # access-token-only row that will die within the hour.
        raise RuntimeError(f"{provider} token exchange returned no refresh_token")

    return {
        "refresh_token": refresh_token,
        "access_token": payload.get("access_token", ""),
        "scope": payload.get("scope", _GOOGLE_SCOPE if provider == "google" else _MS_SCOPE),
    }


async def _refresh_access_token(provider: Provider, refresh_token: str) -> str:
    client_id, client_secret = _client_credentials(provider)
    token_url = _GOOGLE_TOKEN_URL if provider == "google" else _MS_TOKEN_URL
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_url, data=data)
        resp.raise_for_status()
        payload = resp.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(f"{provider} refresh_token exchange returned no access_token")
    return access_token


def _event_payload(provider: Provider, deadline_name: str, domain: str, due: date, source_url: str) -> dict:
    """All-day reminder event on the due date itself. Deliberately no
    reminder/popup override — both providers' account-level default
    notification settings apply, so this doesn't silently fight a user's
    own calendar notification preferences."""
    title = f"[NakTahu] {deadline_name}"
    description = f"{domain} deadline, tracked by NakTahu AI Deadline Monitor.\nSource: {source_url}"
    due_iso = due.isoformat()
    next_day_iso = (due + timedelta(days=1)).isoformat()
    if provider == "google":
        return {
            "summary": title,
            "description": description,
            "start": {"date": due_iso},
            "end": {"date": next_day_iso},
        }
    return {
        "subject": title,
        "body": {"contentType": "text", "content": description},
        "start": {"dateTime": f"{due_iso}T00:00:00", "timeZone": "Asia/Kuala_Lumpur"},
        "end": {"dateTime": f"{next_day_iso}T00:00:00", "timeZone": "Asia/Kuala_Lumpur"},
        "isAllDay": True,
    }


async def _create_event(provider: Provider, access_token: str, calendar_id: str, payload: dict) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        if provider == "google":
            cal = calendar_id or "primary"
            resp = await client.post(f"{_GOOGLE_CALENDAR_API}/calendars/{cal}/events", json=payload, headers=headers)
        else:
            resp = await client.post(f"{_MS_GRAPH_API}/me/events", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["id"]


async def _update_event(provider: Provider, access_token: str, calendar_id: str, event_id: str, payload: dict) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        if provider == "google":
            cal = calendar_id or "primary"
            resp = await client.patch(f"{_GOOGLE_CALENDAR_API}/calendars/{cal}/events/{event_id}", json=payload, headers=headers)
        else:
            resp = await client.patch(f"{_MS_GRAPH_API}/me/events/{event_id}", json=payload, headers=headers)
        resp.raise_for_status()


async def _delete_event(provider: Provider, access_token: str, calendar_id: str, event_id: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        if provider == "google":
            cal = calendar_id or "primary"
            resp = await client.delete(f"{_GOOGLE_CALENDAR_API}/calendars/{cal}/events/{event_id}", headers=headers)
        else:
            resp = await client.delete(f"{_MS_GRAPH_API}/me/events/{event_id}", headers=headers)
        # 404/410 means the event is already gone (user deleted it manually
        # in their calendar app) — that's the desired end state, not a
        # failure worth surfacing.
        if resp.status_code not in (204, 200, 404, 410):
            resp.raise_for_status()


async def sync_deadline_to_connection(
    supabase,
    connection: dict,
    entry: dict,
) -> None:
    """Create or update the calendar event for one (connection, deadline)
    pair. Never raises past this function — a failure is recorded on the
    connection row (last_error) and logged, so one broken connection can't
    take down the whole cron run the way _dispatch_alert's per-user email
    try/except already protects against for email."""
    provider: Provider = connection["provider"]
    user_id = connection["user_id"]
    calendar_id = connection.get("calendar_id") or "primary"
    due = entry["due_date"]
    if isinstance(due, str):
        due = date.fromisoformat(due)

    try:
        existing = (
            supabase.table("calendar_event_links")
            .select("*")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .eq("deadline_schedule_id", entry["id"])
            .execute()
        )
        link = (existing.data or [None])[0]

        if link and link["last_pushed_due_date"] == due.isoformat():
            return  # already up to date — skip the token refresh entirely,
            # not just the push, since there's nothing to push it for.

        access_token = await _refresh_access_token(provider, decrypt_token(connection["encrypted_refresh_token"]))
        payload = _event_payload(provider, entry["deadline_name"], entry["domain"], due, entry.get("source_url") or "")

        if link:
            await _update_event(provider, access_token, calendar_id, link["external_event_id"], payload)
            supabase.table("calendar_event_links").update({
                "last_pushed_due_date": due.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", link["id"]).execute()
        else:
            external_id = await _create_event(provider, access_token, calendar_id, payload)
            supabase.table("calendar_event_links").insert({
                "user_id": user_id,
                "provider": provider,
                "deadline_schedule_id": entry["id"],
                "external_event_id": external_id,
                "last_pushed_due_date": due.isoformat(),
            }).execute()

        supabase.table("calendar_connections").update({
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
        }).eq("id", connection["id"]).execute()

    except Exception as exc:  # noqa: BLE001 — one connection's failure must not kill the run
        log.error("calendar_sync_failed", provider=provider, user_id=user_id, deadline_id=entry.get("id"), error=str(exc))
        supabase.table("calendar_connections").update({
            "last_error": str(exc)[:500],
        }).eq("id", connection["id"]).execute()


async def disconnect(supabase, user_id: str, provider: Provider) -> None:
    """Best-effort revoke at the provider, then delete the local row
    regardless of whether the revoke call succeeded — a user who clicks
    Disconnect must see the connection gone even if the provider's revoke
    endpoint is unreachable."""
    row = (
        supabase.table("calendar_connections")
        .select("*")
        .eq("user_id", user_id)
        .eq("provider", provider)
        .execute()
    )
    connection = (row.data or [None])[0]
    if connection:
        try:
            refresh_token = decrypt_token(connection["encrypted_refresh_token"])
            if provider == "google":
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post("https://oauth2.googleapis.com/revoke", data={"token": refresh_token})
            # Microsoft Graph has no token-revocation endpoint equivalent to
            # Google's — deleting the local row (below) is the only action
            # available; the user can also revoke consent directly from
            # myaccount.microsoft.com if they want to.
        except Exception as exc:  # noqa: BLE001 — best-effort only
            log.warning("calendar_revoke_failed", provider=provider, user_id=user_id, error=str(exc))

    supabase.table("calendar_connections").delete().eq("user_id", user_id).eq("provider", provider).execute()
