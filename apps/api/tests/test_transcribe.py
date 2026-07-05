"""Tests for the Google Speech-to-Text service + /api/v1/transcribe endpoint."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import transcribe as transcribe_router
from app.services import speech

_FAKE_GOOGLE_RESPONSE = {
    "results": [
        {
            "alternatives": [{"transcript": "berapa kadar cukai", "confidence": 0.94}],
            "languageCode": "ms-MY",
        }
    ]
}

_VALID_B64 = "QUJDQUJDQUJDQUJD"  # 16 chars — clears the min_length guard


# --- service: app.services.speech -----------------------------------------


@pytest.mark.asyncio
async def test_transcribe_parses_response(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SPEECH_API_KEY", "test-key")
    monkeypatch.setattr(speech, "_call_google", AsyncMock(return_value=_FAKE_GOOGLE_RESPONSE))

    result = await speech.transcribe(_VALID_B64, "bm")

    assert result["transcript"] == "berapa kadar cukai"
    assert result["confidence"] == 0.94
    assert result["detected_language"] == "bm"


@pytest.mark.asyncio
async def test_transcribe_builds_webm_opus_multilingual_payload(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SPEECH_API_KEY", "test-key")
    captured: dict = {}

    async def fake_call(url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return _FAKE_GOOGLE_RESPONSE

    monkeypatch.setattr(speech, "_call_google", fake_call)
    await speech.transcribe(_VALID_B64, "bm")

    cfg = captured["payload"]["config"]
    assert cfg["encoding"] == "WEBM_OPUS"
    assert cfg["sampleRateHertz"] == 48000
    assert cfg["languageCode"] == "ms-MY"
    assert cfg["alternativeLanguageCodes"] == ["en-MY", "cmn-Hans-CN"]
    assert cfg["enableAutomaticPunctuation"] is True
    assert cfg["model"] == "latest_short"
    assert captured["payload"]["audio"]["content"] == _VALID_B64
    assert "key=test-key" in captured["url"]


@pytest.mark.asyncio
async def test_transcribe_detects_mandarin(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SPEECH_API_KEY", "k")
    monkeypatch.setattr(
        speech,
        "_call_google",
        AsyncMock(return_value={
            "results": [{
                "alternatives": [{"transcript": "你好", "confidence": 0.8}],
                "languageCode": "cmn-Hans-CN",
            }]
        }),
    )
    result = await speech.transcribe(_VALID_B64, "bm")  # requested bm, spoke zh
    assert result["detected_language"] == "zh"


@pytest.mark.asyncio
async def test_transcribe_raises_config_error_without_key(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_SPEECH_API_KEY", raising=False)
    with pytest.raises(speech.SpeechConfigError):
        await speech.transcribe(_VALID_B64, "bm")


@pytest.mark.asyncio
async def test_transcribe_wraps_upstream_error(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SPEECH_API_KEY", "k")

    async def boom(url, payload):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(speech, "_call_google", boom)
    with pytest.raises(speech.SpeechServiceError):
        await speech.transcribe(_VALID_B64, "bm")


# --- endpoint: /api/v1/transcribe -----------------------------------------


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(transcribe_router.router)
    return TestClient(app)


def test_endpoint_returns_transcript() -> None:
    fake = AsyncMock(return_value={"transcript": "hai", "confidence": 0.9, "detected_language": "bm"})
    with patch.object(transcribe_router, "transcribe_audio", fake):
        resp = _client().post("/api/v1/transcribe", json={"audio_base64": _VALID_B64, "language": "bm"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "hai"
    assert body["detected_language"] == "bm"


def test_endpoint_503_when_not_configured() -> None:
    fake = AsyncMock(side_effect=speech.SpeechConfigError())
    with patch.object(transcribe_router, "transcribe_audio", fake):
        resp = _client().post("/api/v1/transcribe", json={"audio_base64": _VALID_B64, "language": "bm"})
    assert resp.status_code == 503


def test_endpoint_502_on_service_error() -> None:
    fake = AsyncMock(side_effect=speech.SpeechServiceError())
    with patch.object(transcribe_router, "transcribe_audio", fake):
        resp = _client().post("/api/v1/transcribe", json={"audio_base64": _VALID_B64, "language": "bm"})
    assert resp.status_code == 502


def test_endpoint_422_on_too_short_audio() -> None:
    resp = _client().post("/api/v1/transcribe", json={"audio_base64": "abc", "language": "bm"})
    assert resp.status_code == 422
