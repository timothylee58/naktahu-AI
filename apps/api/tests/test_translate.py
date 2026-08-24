"""Tests for the /chat translate control's backend — services/translate.py
(ILMU-primary/Anthropic-fallback text translation) and routers/translate.py
(auth boundary, validation, happy path)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware.rate_limit import authenticated_limiter
from services.translate import translate_text


def _mock_ilmu_response(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_anthropic_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


# ── Service layer ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_uses_ilmu_when_it_succeeds(monkeypatch):
    resp = _mock_ilmu_response("你好，世界")
    monkeypatch.setattr("services.translate.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))
    anthropic_mock = AsyncMock()
    monkeypatch.setattr("services.translate.anthropic_client.messages.create", anthropic_mock)

    result = await translate_text("Hello, world", "zh")

    assert result == "你好，世界"
    anthropic_mock.assert_not_called()


@pytest.mark.asyncio
async def test_translate_falls_back_to_anthropic_when_ilmu_raises(monkeypatch):
    monkeypatch.setattr(
        "services.translate.ilmu_client.chat.completions.create",
        AsyncMock(side_effect=RuntimeError("ILMU unavailable")),
    )
    resp = _mock_anthropic_response("Selamat pagi")
    monkeypatch.setattr("services.translate.anthropic_client.messages.create", AsyncMock(return_value=resp))

    result = await translate_text("Good morning", "bm")

    assert result == "Selamat pagi"


@pytest.mark.asyncio
async def test_translate_falls_back_to_anthropic_when_ilmu_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "services.translate.ilmu_client.chat.completions.create",
        AsyncMock(return_value=_mock_ilmu_response("")),
    )
    resp = _mock_anthropic_response("fallback translation")
    monkeypatch.setattr("services.translate.anthropic_client.messages.create", AsyncMock(return_value=resp))

    result = await translate_text("text", "en")

    assert result == "fallback translation"


@pytest.mark.asyncio
async def test_translate_degrades_to_empty_string_when_both_providers_fail(monkeypatch):
    monkeypatch.setattr(
        "services.translate.ilmu_client.chat.completions.create",
        AsyncMock(side_effect=RuntimeError("ILMU unavailable")),
    )
    monkeypatch.setattr(
        "services.translate.anthropic_client.messages.create",
        AsyncMock(side_effect=RuntimeError("Anthropic unavailable")),
    )

    result = await translate_text("text", "en")

    assert result == ""


# ── Router ───────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from routers import translate as router_module

    app = FastAPI()
    app.include_router(router_module.router)
    authenticated_limiter.reset()
    with TestClient(app) as c:
        yield c


def test_post_translate_happy_path_anonymous(client):
    """Anonymous (no auth header) works — translation isn't a gated
    feature, matching /query's own optional-auth tier."""
    with patch("routers.translate.translate_text", new=AsyncMock(return_value="你好")):
        res = client.post("/api/v1/translate", json={"text": "Hello", "target_language": "zh"})
    assert res.status_code == 200
    assert res.json() == {"translated_text": "你好", "target_language": "zh"}


def test_post_translate_normalises_ms_to_bm(client):
    with patch("routers.translate.translate_text", new=AsyncMock(return_value="Selamat")) as mock_translate:
        res = client.post("/api/v1/translate", json={"text": "Hi", "target_language": "ms"})
    assert res.status_code == 200
    assert res.json()["target_language"] == "bm"
    mock_translate.assert_awaited_once_with("Hi", "bm")


def test_post_translate_422_on_empty_text(client):
    res = client.post("/api/v1/translate", json={"text": "", "target_language": "en"})
    assert res.status_code == 422


def test_post_translate_422_on_oversized_text(client):
    res = client.post("/api/v1/translate", json={"text": "x" * 8001, "target_language": "en"})
    assert res.status_code == 422


def test_post_translate_422_on_invalid_language(client):
    res = client.post("/api/v1/translate", json={"text": "Hello", "target_language": "fr"})
    assert res.status_code == 422


def test_post_translate_502_when_both_providers_fail(client):
    with patch("routers.translate.translate_text", new=AsyncMock(return_value="")):
        res = client.post("/api/v1/translate", json={"text": "Hello", "target_language": "zh"})
    assert res.status_code == 502


def test_post_translate_works_without_supabase():
    """No Supabase dependency at all — must keep working in degraded mode."""
    from routers import translate as router_module

    app = FastAPI()
    app.include_router(router_module.router)
    app.state.supabase = None
    authenticated_limiter.reset()

    with TestClient(app) as c:
        with patch("routers.translate.translate_text", new=AsyncMock(return_value="Bonjour")):
            res = c.post("/api/v1/translate", json={"text": "Hello", "target_language": "en"})
    assert res.status_code == 200
