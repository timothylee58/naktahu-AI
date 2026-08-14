"""Tests for app.agents.tools.ocr_extract_text — ILMU-primary,
Anthropic-fallback vision transcription used by Study Agent's photo intake."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.tools import ocr_extract_text


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


@pytest.mark.asyncio
async def test_ocr_uses_ilmu_when_it_succeeds(monkeypatch):
    resp = _mock_ilmu_response("Soalan 1: transcribed via ILMU")
    monkeypatch.setattr("app.agents.tools.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))
    anthropic_mock = AsyncMock()
    monkeypatch.setattr("app.services.llm_client.anthropic_client.messages.create", anthropic_mock)

    result = await ocr_extract_text("ZmFrZQ==", mime_type="image/jpeg", language="bm")

    assert result == "Soalan 1: transcribed via ILMU"
    anthropic_mock.assert_not_called()


@pytest.mark.asyncio
async def test_ocr_falls_back_to_anthropic_when_ilmu_raises(monkeypatch):
    monkeypatch.setattr(
        "app.agents.tools.ilmu_client.chat.completions.create",
        AsyncMock(side_effect=RuntimeError("ILMU unavailable")),
    )
    resp = _mock_anthropic_response("Soalan 1: transcribed via Anthropic fallback")
    monkeypatch.setattr("app.services.llm_client.anthropic_client.messages.create", AsyncMock(return_value=resp))

    result = await ocr_extract_text("ZmFrZQ==", mime_type="image/png", language="en")

    assert result == "Soalan 1: transcribed via Anthropic fallback"


@pytest.mark.asyncio
async def test_ocr_falls_back_to_anthropic_when_ilmu_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "app.agents.tools.ilmu_client.chat.completions.create",
        AsyncMock(return_value=_mock_ilmu_response("")),
    )
    resp = _mock_anthropic_response("fallback text")
    monkeypatch.setattr("app.services.llm_client.anthropic_client.messages.create", AsyncMock(return_value=resp))

    result = await ocr_extract_text("ZmFrZQ==")

    assert result == "fallback text"


@pytest.mark.asyncio
async def test_ocr_degrades_to_empty_string_when_both_providers_fail(monkeypatch):
    """Trap #4-style degrade: never raise out of a node — the caller
    (intake_node) falls back to any manually-typed paper_text instead."""
    monkeypatch.setattr(
        "app.agents.tools.ilmu_client.chat.completions.create",
        AsyncMock(side_effect=RuntimeError("ILMU unavailable")),
    )
    monkeypatch.setattr(
        "app.services.llm_client.anthropic_client.messages.create",
        AsyncMock(side_effect=RuntimeError("Anthropic unavailable")),
    )

    result = await ocr_extract_text("ZmFrZQ==")

    assert result == ""
