"""Tests for app.agents.tools.ocr_extract_text — ILMU-primary,
Anthropic-fallback vision transcription used by Study Agent's photo intake."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.tools import ocr_extract_listing_fields, ocr_extract_text


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


# ── ocr_extract_listing_fields — same ILMU-primary/Anthropic-fallback
# shape, but structured JSON output for property_listing_submissions'
# prefill flow instead of raw transcribed text. ──────────────────────────

@pytest.mark.asyncio
async def test_listing_ocr_parses_ilmu_json_response(monkeypatch):
    resp = _mock_ilmu_response(
        '{"title": "Nice condo in PJ", "price_myr": 500000, "location": "Petaling Jaya", '
        '"property_type": "condo", "bedrooms": 3}'
    )
    monkeypatch.setattr("app.agents.tools.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))
    anthropic_mock = AsyncMock()
    monkeypatch.setattr("app.services.llm_client.anthropic_client.messages.create", anthropic_mock)

    result = await ocr_extract_listing_fields("ZmFrZQ==")

    assert result == {
        "title": "Nice condo in PJ",
        "price_myr": 500000.0,
        "location": "Petaling Jaya",
        "property_type": "condo",
        "bedrooms": 3,
    }
    anthropic_mock.assert_not_called()


@pytest.mark.asyncio
async def test_listing_ocr_drops_null_and_invalid_fields():
    """The model is told to use null for anything unreadable — those keys
    must be OMITTED from the result (not stored as literal None), and an
    out-of-enum property_type or a nonsense bedroom count must be dropped
    rather than passed through to the submission form."""
    resp = _mock_ilmu_response(
        '{"title": null, "price_myr": null, "location": "Cheras", '
        '"property_type": "castle", "bedrooms": 999}'
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.agents.tools.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))
        result = await ocr_extract_listing_fields("ZmFrZQ==")

    assert result == {"location": "Cheras"}


@pytest.mark.asyncio
async def test_listing_ocr_falls_back_to_anthropic_when_ilmu_returns_empty(monkeypatch):
    monkeypatch.setattr(
        "app.agents.tools.ilmu_client.chat.completions.create",
        AsyncMock(return_value=_mock_ilmu_response("")),
    )
    resp = _mock_anthropic_response('{"title": "Via fallback", "location": null}')
    monkeypatch.setattr("app.services.llm_client.anthropic_client.messages.create", AsyncMock(return_value=resp))

    result = await ocr_extract_listing_fields("ZmFrZQ==")

    assert result == {"title": "Via fallback"}


@pytest.mark.asyncio
async def test_listing_ocr_degrades_to_empty_dict_when_both_providers_fail(monkeypatch):
    monkeypatch.setattr(
        "app.agents.tools.ilmu_client.chat.completions.create",
        AsyncMock(side_effect=RuntimeError("ILMU unavailable")),
    )
    monkeypatch.setattr(
        "app.services.llm_client.anthropic_client.messages.create",
        AsyncMock(side_effect=RuntimeError("Anthropic unavailable")),
    )

    result = await ocr_extract_listing_fields("ZmFrZQ==")

    assert result == {}


@pytest.mark.asyncio
async def test_listing_ocr_degrades_to_empty_dict_on_unparseable_response(monkeypatch):
    monkeypatch.setattr(
        "app.agents.tools.ilmu_client.chat.completions.create",
        AsyncMock(return_value=_mock_ilmu_response("Sorry, I can't read this image clearly.")),
    )
    monkeypatch.setattr(
        "app.services.llm_client.anthropic_client.messages.create",
        AsyncMock(side_effect=RuntimeError("Anthropic unavailable")),
    )

    result = await ocr_extract_listing_fields("ZmFrZQ==")

    assert result == {}
