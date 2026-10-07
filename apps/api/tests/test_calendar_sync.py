"""Unit tests for services/calendar_sync.py and app/services/token_encryption.py
— the OAuth/token/event-building logic, independent of the FastAPI app.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.services import token_encryption
from services import calendar_sync


# ---------------------------------------------------------------------------
# token_encryption
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_round_trip(monkeypatch):
    monkeypatch.setattr(
        token_encryption.settings, "calendar_token_encryption_key", Fernet.generate_key().decode()
    )
    ciphertext = token_encryption.encrypt_token("my-refresh-token")
    assert ciphertext != "my-refresh-token"
    assert token_encryption.decrypt_token(ciphertext) == "my-refresh-token"


def test_encrypt_raises_when_key_unset(monkeypatch):
    monkeypatch.setattr(token_encryption.settings, "calendar_token_encryption_key", "")
    with pytest.raises(token_encryption.TokenEncryptionUnavailable):
        token_encryption.encrypt_token("secret")


def test_decrypt_raises_on_wrong_key(monkeypatch):
    monkeypatch.setattr(
        token_encryption.settings, "calendar_token_encryption_key", Fernet.generate_key().decode()
    )
    ciphertext = token_encryption.encrypt_token("secret")
    monkeypatch.setattr(
        token_encryption.settings, "calendar_token_encryption_key", Fernet.generate_key().decode()
    )
    with pytest.raises(token_encryption.TokenEncryptionUnavailable):
        token_encryption.decrypt_token(ciphertext)


# ---------------------------------------------------------------------------
# OAuth state (Redis-backed, one-time use)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oauth_state_round_trip():
    store: dict[str, str] = {}
    redis_client = AsyncMock()
    redis_client.setex = AsyncMock(side_effect=lambda k, ttl, v: store.__setitem__(k, v))
    redis_client.get = AsyncMock(side_effect=lambda k: store.get(k))
    redis_client.delete = AsyncMock(side_effect=lambda k: store.pop(k, None))

    state = await calendar_sync.create_oauth_state(redis_client, "user-123")
    user_id = await calendar_sync.consume_oauth_state(redis_client, state)
    assert user_id == "user-123"

    # One-time use — a second consume of the same state must fail.
    again = await calendar_sync.consume_oauth_state(redis_client, state)
    assert again is None


@pytest.mark.asyncio
async def test_oauth_state_unknown_returns_none():
    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=None)
    assert await calendar_sync.consume_oauth_state(redis_client, "not-a-real-state") is None


# ---------------------------------------------------------------------------
# authorize URL / config-missing handling
# ---------------------------------------------------------------------------

def test_build_authorize_url_raises_without_config(monkeypatch):
    monkeypatch.setattr(calendar_sync.settings, "google_calendar_client_id", "")
    monkeypatch.setattr(calendar_sync.settings, "google_calendar_client_secret", "")
    with pytest.raises(calendar_sync.CalendarConfigMissing):
        calendar_sync.build_authorize_url("google", "state123")


def test_build_authorize_url_google(monkeypatch):
    monkeypatch.setattr(calendar_sync.settings, "google_calendar_client_id", "gid")
    monkeypatch.setattr(calendar_sync.settings, "google_calendar_client_secret", "gsecret")
    url = calendar_sync.build_authorize_url("google", "state123")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=gid" in url
    assert "state=state123" in url
    assert "calendar.events" in url


def test_build_authorize_url_microsoft(monkeypatch):
    monkeypatch.setattr(calendar_sync.settings, "microsoft_calendar_client_id", "mid")
    monkeypatch.setattr(calendar_sync.settings, "microsoft_calendar_client_secret", "msecret")
    url = calendar_sync.build_authorize_url("microsoft", "state456")
    assert url.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize?")
    assert "client_id=mid" in url
    assert "Calendars.ReadWrite" in url


# ---------------------------------------------------------------------------
# token exchange
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exchange_code_for_tokens_raises_without_refresh_token(monkeypatch):
    monkeypatch.setattr(calendar_sync.settings, "google_calendar_client_id", "gid")
    monkeypatch.setattr(calendar_sync.settings, "google_calendar_client_secret", "gsecret")

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"access_token": "at-only"}  # no refresh_token

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=resp)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patch("services.calendar_sync.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="no refresh_token"):
            await calendar_sync.exchange_code_for_tokens("google", "authcode")


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_happy_path(monkeypatch):
    monkeypatch.setattr(calendar_sync.settings, "google_calendar_client_id", "gid")
    monkeypatch.setattr(calendar_sync.settings, "google_calendar_client_secret", "gsecret")

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"access_token": "at", "refresh_token": "rt", "scope": "calendar.events"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=resp)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False

    with patch("services.calendar_sync.httpx.AsyncClient", return_value=mock_client):
        tokens = await calendar_sync.exchange_code_for_tokens("google", "authcode")

    assert tokens == {"refresh_token": "rt", "access_token": "at", "scope": "calendar.events"}


# ---------------------------------------------------------------------------
# event payload — never claims write-only where the API doesn't support it
# ---------------------------------------------------------------------------

def test_event_payload_google_is_all_day():
    payload = calendar_sync._event_payload(
        "google", "Cukai Pendapatan", "tax", date(2026, 4, 30), "https://www.hasil.gov.my"
    )
    assert payload["start"] == {"date": "2026-04-30"}
    assert payload["end"] == {"date": "2026-05-01"}
    assert "[NakTahu]" in payload["summary"]


def test_event_payload_microsoft_is_all_day():
    payload = calendar_sync._event_payload(
        "microsoft", "EPF Contribution", "epf", date(2026, 4, 30), "https://www.kwsp.gov.my"
    )
    assert payload["isAllDay"] is True
    assert payload["start"]["dateTime"].startswith("2026-04-30")


# ---------------------------------------------------------------------------
# sync_deadline_to_connection — the per-(connection, deadline) push
# ---------------------------------------------------------------------------

def _table_mock_for_sync(existing_link: dict | None):
    """Builds a MagicMock mirroring supabase-py's fluent .table(...).select()...
    chain, returning `existing_link` (or none) for calendar_event_links reads,
    and no-oping every write."""
    execute_result = MagicMock()
    execute_result.data = [existing_link] if existing_link else []

    query_chain = MagicMock()
    query_chain.select.return_value = query_chain
    query_chain.eq.return_value = query_chain
    query_chain.execute.return_value = execute_result
    query_chain.insert.return_value.execute.return_value = MagicMock()
    query_chain.update.return_value.eq.return_value.execute.return_value = MagicMock()

    sb = MagicMock()
    sb.table.return_value = query_chain
    return sb


@pytest.mark.asyncio
async def test_sync_creates_new_event_when_no_link_exists(monkeypatch):
    monkeypatch.setattr(
        calendar_sync, "decrypt_token", lambda _: "plain-refresh-token"
    )
    monkeypatch.setattr(calendar_sync, "_refresh_access_token", AsyncMock(return_value="access-tok"))
    create_mock = AsyncMock(return_value="ext-event-1")
    monkeypatch.setattr(calendar_sync, "_create_event", create_mock)

    sb = _table_mock_for_sync(existing_link=None)
    connection = {"id": "conn-1", "provider": "google", "user_id": "u1", "calendar_id": "primary",
                  "encrypted_refresh_token": "enc"}
    entry = {"id": "d1", "deadline_name": "Cukai", "domain": "tax", "due_date": "2026-04-30", "source_url": "x"}

    await calendar_sync.sync_deadline_to_connection(sb, connection, entry)

    create_mock.assert_awaited_once()
    # last_error cleared, last_synced_at set — the success path, not the
    # except-branch that records last_error.
    update_calls = [c for c in sb.table.return_value.update.call_args_list]
    assert any("last_synced_at" in c.args[0] for c in update_calls)


@pytest.mark.asyncio
async def test_sync_skips_when_already_up_to_date(monkeypatch):
    monkeypatch.setattr(calendar_sync, "decrypt_token", lambda _: "plain-refresh-token")
    refresh_mock = AsyncMock(return_value="access-tok")
    monkeypatch.setattr(calendar_sync, "_refresh_access_token", refresh_mock)
    update_mock = AsyncMock()
    monkeypatch.setattr(calendar_sync, "_update_event", update_mock)

    sb = _table_mock_for_sync(existing_link={
        "id": "link1", "external_event_id": "ext-1", "last_pushed_due_date": "2026-04-30",
    })
    connection = {"id": "conn-1", "provider": "google", "user_id": "u1", "calendar_id": "primary",
                  "encrypted_refresh_token": "enc"}
    entry = {"id": "d1", "deadline_name": "Cukai", "domain": "tax", "due_date": "2026-04-30", "source_url": "x"}

    await calendar_sync.sync_deadline_to_connection(sb, connection, entry)

    # Already pushed for this exact due_date — no update call, no token refresh.
    update_mock.assert_not_awaited()
    refresh_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_updates_existing_event_on_date_drift(monkeypatch):
    monkeypatch.setattr(calendar_sync, "decrypt_token", lambda _: "plain-refresh-token")
    monkeypatch.setattr(calendar_sync, "_refresh_access_token", AsyncMock(return_value="access-tok"))
    update_mock = AsyncMock()
    monkeypatch.setattr(calendar_sync, "_update_event", update_mock)

    sb = _table_mock_for_sync(existing_link={
        "id": "link1", "external_event_id": "ext-1", "last_pushed_due_date": "2026-04-15",
    })
    connection = {"id": "conn-1", "provider": "google", "user_id": "u1", "calendar_id": "primary",
                  "encrypted_refresh_token": "enc"}
    entry = {"id": "d1", "deadline_name": "Cukai", "domain": "tax", "due_date": "2026-04-30", "source_url": "x"}

    await calendar_sync.sync_deadline_to_connection(sb, connection, entry)

    update_mock.assert_awaited_once()
    args = update_mock.call_args.args
    assert args[:4] == ("google", "access-tok", "primary", "ext-1")
    pushed_payload = args[4]
    assert pushed_payload["start"] == {"date": "2026-04-30"}  # the drifted date, not the stale 04-15


@pytest.mark.asyncio
async def test_sync_records_last_error_on_failure_without_raising(monkeypatch):
    monkeypatch.setattr(calendar_sync, "decrypt_token", lambda _: "plain-refresh-token")
    monkeypatch.setattr(
        calendar_sync, "_refresh_access_token", AsyncMock(side_effect=RuntimeError("token revoked"))
    )

    sb = _table_mock_for_sync(existing_link=None)
    connection = {"id": "conn-1", "provider": "google", "user_id": "u1", "calendar_id": "primary",
                  "encrypted_refresh_token": "enc"}
    entry = {"id": "d1", "deadline_name": "Cukai", "domain": "tax", "due_date": "2026-04-30", "source_url": "x"}

    # Must not raise — one broken connection can't kill the whole cron run.
    await calendar_sync.sync_deadline_to_connection(sb, connection, entry)

    update_calls = sb.table.return_value.update.call_args_list
    assert any("last_error" in c.args[0] and c.args[0]["last_error"] for c in update_calls)
