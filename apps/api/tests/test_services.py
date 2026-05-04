"""Unit tests for services/auth.py and services/history.py."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest

from core.config import settings
from services.auth import _decode_supabase_jwt, get_current_user
from services.history import fetch_history_entries, history_key, persist_session_entry


# ---------------------------------------------------------------------------
# services/auth — _decode_supabase_jwt
# ---------------------------------------------------------------------------


def test_decode_jwt_invalid_token_returns_none():
    result = _decode_supabase_jwt("this.is.not.a.valid.jwt")
    assert result is None


def test_decode_jwt_expired_token_returns_none():
    token = jwt.encode(
        {"sub": "user-1", "aud": settings.supabase_jwt_aud, "exp": int(time.time()) - 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    result = _decode_supabase_jwt(token)
    assert result is None


def test_decode_jwt_missing_sub_returns_none():
    token = jwt.encode(
        {"aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    result = _decode_supabase_jwt(token)
    assert result is None


def test_decode_jwt_non_string_sub_returns_none():
    token = jwt.encode(
        {"sub": 99999, "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    result = _decode_supabase_jwt(token)
    assert result is None


def test_decode_jwt_empty_string_sub_returns_none():
    token = jwt.encode(
        {"sub": "", "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    result = _decode_supabase_jwt(token)
    assert result is None


def test_decode_jwt_valid_token_returns_user_context():
    token = jwt.encode(
        {"sub": "user-abc", "aud": settings.supabase_jwt_aud, "exp": int(time.time()) + 3600},
        settings.jwt_secret,
        algorithm="HS256",
    )
    result = _decode_supabase_jwt(token)
    assert result is not None
    assert result.user_id == "user-abc"
    assert result.is_anonymous is False


# ---------------------------------------------------------------------------
# services/auth — get_current_user
# ---------------------------------------------------------------------------


def test_get_current_user_no_token_raises_401():
    from fastapi import HTTPException

    async def run():
        return await get_current_user(token=None)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(run())
    assert exc_info.value.status_code == 401


def test_get_current_user_invalid_token_raises_401():
    from fastapi import HTTPException

    async def run():
        return await get_current_user(token="invalid.token.here")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(run())
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# services/history — history_key
# ---------------------------------------------------------------------------


def test_history_key_format():
    assert history_key("user-abc") == "session_history:user-abc"
    assert history_key("another") == "session_history:another"


# ---------------------------------------------------------------------------
# services/history — fetch_history_entries
# ---------------------------------------------------------------------------


async def test_fetch_history_entries_empty_list():
    redis_mock = AsyncMock()
    redis_mock.lrange = AsyncMock(return_value=[])
    result = await fetch_history_entries(redis_mock, "user-1")
    assert result == []
    redis_mock.lrange.assert_called_once_with("session_history:user-1", 0, 19)


async def test_fetch_history_entries_returns_decoded_entries():
    entry = {"query": "What is VAT?", "language": "en", "domain": "tax"}
    redis_mock = AsyncMock()
    redis_mock.lrange = AsyncMock(return_value=[json.dumps(entry)])
    result = await fetch_history_entries(redis_mock, "user-1")
    assert len(result) == 1
    assert result[0]["query"] == "What is VAT?"


async def test_fetch_history_entries_skips_invalid_json():
    valid_entry = json.dumps({"query": "ok"})
    redis_mock = AsyncMock()
    redis_mock.lrange = AsyncMock(return_value=["{bad json", "not-json-at-all", valid_entry])
    result = await fetch_history_entries(redis_mock, "user-1")
    assert len(result) == 1
    assert result[0]["query"] == "ok"


async def test_fetch_history_entries_multiple_items():
    entries = [json.dumps({"query": f"q{i}"}) for i in range(5)]
    redis_mock = AsyncMock()
    redis_mock.lrange = AsyncMock(return_value=entries)
    result = await fetch_history_entries(redis_mock, "user-1")
    assert len(result) == 5


# ---------------------------------------------------------------------------
# services/history — persist_session_entry
# ---------------------------------------------------------------------------


def _make_redis_mock():
    redis_mock = AsyncMock()
    pipe = MagicMock()
    pipe.lpush.return_value = pipe
    pipe.ltrim.return_value = pipe
    pipe.execute = AsyncMock(return_value=[1, True])
    redis_mock.pipeline = MagicMock(return_value=pipe)
    return redis_mock, pipe


def _make_supabase_mock():
    sb = MagicMock()
    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[{}])
    sb.table.return_value.insert.return_value = insert_mock
    return sb, insert_mock


async def test_persist_session_entry_truncates_long_response():
    redis_mock, pipe = _make_redis_mock()
    sb, _ = _make_supabase_mock()

    await persist_session_entry(
        redis_client=redis_mock,
        supabase_client=sb,
        user_id="user-1",
        query="test",
        language="en",
        domain="general",
        response_text="A" * 300,
        citations=[],
    )

    call_args = pipe.lpush.call_args[0]
    stored_entry = json.loads(call_args[1])
    assert len(stored_entry["response_summary"]) == 150


async def test_persist_session_entry_short_response_not_truncated():
    redis_mock, pipe = _make_redis_mock()
    sb, _ = _make_supabase_mock()

    short_text = "Short answer."
    await persist_session_entry(
        redis_client=redis_mock,
        supabase_client=sb,
        user_id="user-1",
        query="test",
        language="en",
        domain="general",
        response_text=short_text,
        citations=[],
    )

    call_args = pipe.lpush.call_args[0]
    stored_entry = json.loads(call_args[1])
    assert stored_entry["response_summary"] == short_text


async def test_persist_session_entry_calls_redis_pipeline():
    redis_mock, pipe = _make_redis_mock()
    sb, _ = _make_supabase_mock()

    await persist_session_entry(
        redis_client=redis_mock,
        supabase_client=sb,
        user_id="user-1",
        query="test",
        language="en",
        domain="general",
        response_text="response",
        citations=[{"url": "https://example.com"}],
    )

    redis_mock.pipeline.assert_called_once()
    pipe.lpush.assert_called_once()
    pipe.ltrim.assert_called_once()
    pipe.execute.assert_called_once()


async def test_persist_session_entry_calls_supabase_insert():
    redis_mock, _ = _make_redis_mock()
    sb, insert_mock = _make_supabase_mock()

    await persist_session_entry(
        redis_client=redis_mock,
        supabase_client=sb,
        user_id="user-42",
        query="income tax",
        language="ms",
        domain="tax",
        response_text="answer",
        citations=[],
    )

    sb.table.assert_called_with("user_sessions")
    insert_mock.execute.assert_called_once()


async def test_persist_session_entry_stores_correct_fields():
    redis_mock, pipe = _make_redis_mock()
    sb, _ = _make_supabase_mock()

    await persist_session_entry(
        redis_client=redis_mock,
        supabase_client=sb,
        user_id="user-1",
        query="What is GST?",
        language="ms",
        domain="tax",
        response_text="GST is a goods and services tax.",
        citations=[{"url": "https://example.com"}],
    )

    call_args = pipe.lpush.call_args[0]
    stored_entry = json.loads(call_args[1])
    assert stored_entry["query"] == "What is GST?"
    assert stored_entry["language"] == "ms"
    assert stored_entry["domain"] == "tax"
    assert "ts" in stored_entry
