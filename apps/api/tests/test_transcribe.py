"""Tests for Google Speech-to-Text V2 service + /api/v1/transcribe endpoints."""
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
_FAKE_CREDS_JSON = '{"type":"service_account","project_id":"test-proj","private_key_id":"k","private_key":"-----BEGIN PRIVATE KEY-----\\nMIIE\\n-----END PRIVATE KEY-----\\n","client_email":"sa@test.iam.gserviceaccount.com","client_id":"1","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}'


def _configure_speech_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SPEECH_PROJECT_ID", "test-proj")
    monkeypatch.setenv("GOOGLE_SPEECH_LOCATION", "asia-southeast1")
    monkeypatch.setenv("GOOGLE_SPEECH_CREDENTIALS_JSON", _FAKE_CREDS_JSON)
    speech._load_credentials.cache_clear()


# --- service: app.services.speech -----------------------------------------


@pytest.mark.asyncio
async def test_transcribe_parses_response(monkeypatch) -> None:
    _configure_speech_env(monkeypatch)
    monkeypatch.setattr(speech, "_access_token", lambda: "test-token")
    monkeypatch.setattr(speech, "_call_google", AsyncMock(return_value=_FAKE_GOOGLE_RESPONSE))

    result = await speech.transcribe(_VALID_B64, "bm")

    assert result["transcript"] == "berapa kadar cukai"
    assert result["confidence"] == 0.94
    assert result["detected_language"] == "bm"


@pytest.mark.asyncio
async def test_transcribe_builds_chirp3_multilingual_payload(monkeypatch) -> None:
    _configure_speech_env(monkeypatch)
    captured: dict = {}

    async def fake_call(url, payload, token):
        captured["url"] = url
        captured["payload"] = payload
        captured["token"] = token
        return _FAKE_GOOGLE_RESPONSE

    monkeypatch.setattr(speech, "_access_token", lambda: "test-token")
    monkeypatch.setattr(speech, "_call_google", fake_call)
    await speech.transcribe(_VALID_B64, "bm")

    cfg = captured["payload"]["config"]
    assert cfg["autoDecodingConfig"] == {}
    assert cfg["languageCodes"] == ["ms-MY", "en-MY", "cmn-Hans-CN"]
    assert cfg["model"] == "chirp_3"
    assert cfg["features"]["enableAutomaticPunctuation"] is True
    assert captured["payload"]["content"] == _VALID_B64
    assert captured["token"] == "test-token"
    assert "asia-southeast1-speech.googleapis.com" in captured["url"]
    assert "/v2/projects/test-proj/locations/asia-southeast1/recognizers/_:recognize" in captured["url"]


@pytest.mark.asyncio
async def test_transcribe_detects_mandarin(monkeypatch) -> None:
    _configure_speech_env(monkeypatch)
    monkeypatch.setattr(speech, "_access_token", lambda: "t")
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
async def test_transcribe_raises_config_error_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_SPEECH_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SPEECH_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    speech._load_credentials.cache_clear()
    with pytest.raises(speech.SpeechConfigError):
        await speech.transcribe(_VALID_B64, "bm")


@pytest.mark.asyncio
async def test_transcribe_wraps_upstream_error(monkeypatch) -> None:
    _configure_speech_env(monkeypatch)
    monkeypatch.setattr(speech, "_access_token", lambda: "t")

    async def boom(url, payload, token):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(speech, "_call_google", boom)
    with pytest.raises(speech.SpeechServiceError):
        await speech.transcribe(_VALID_B64, "bm")


@pytest.mark.asyncio
async def test_transcribe_stream_yields_events(monkeypatch) -> None:
    _configure_speech_env(monkeypatch)
    monkeypatch.setattr(
        speech,
        "_stream_recognize_sync",
        lambda audio_bytes, language: [
            {"is_final": False, "transcript": "ber", "confidence": 0.5, "detected_language": "bm"},
            {"is_final": True, "transcript": "berapa", "confidence": 0.9, "detected_language": "bm"},
        ],
    )

    events = [event async for event in speech.transcribe_stream(_VALID_B64, "bm")]
    assert len(events) == 2
    assert events[0]["is_final"] is False
    assert events[1]["transcript"] == "berapa"


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


def test_stream_endpoint_emits_sse() -> None:
    async def fake_stream(audio_base64: str, language: str):
        yield {"is_final": False, "transcript": "hai", "confidence": 0.5, "detected_language": "bm"}
        yield {"is_final": True, "transcript": "hai dunia", "confidence": 0.9, "detected_language": "bm"}

    with patch.object(transcribe_router, "transcribe_stream", fake_stream):
        resp = _client().post("/api/v1/transcribe/stream", json={"audio_base64": _VALID_B64, "language": "bm"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "event: interim" in body
    assert "event: final" in body
    assert "event: done" in body
    assert '"text": "hai dunia"' in body
