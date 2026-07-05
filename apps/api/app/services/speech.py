"""Google Cloud Speech-to-Text V2 wrapper (Chirp 3, asia-southeast1).

Cross-browser fallback for the browser Web Speech API: the frontend records mic
audio with MediaRecorder (WEBM/Opus), base64-encodes it, and posts it to
/api/v1/transcribe, which calls this service.

Uses the V2 `recognizers:recognize` REST endpoint with service-account OAuth.
Key notes:
- `autoDecodingConfig` lets Chirp 3 detect WEBM/Opus parameters automatically.
- `languageCodes` carries all BM/EN/ZH locales in one request for code-switching.
- Degrades gracefully: if credentials or project ID are unset, raises
  SpeechConfigError so the API keeps booting (mirrors Redis/Supabase handling).
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
from functools import lru_cache
from typing import Any, AsyncIterator

import httpx
import structlog
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

log = structlog.get_logger(__name__)

_DEFAULT_LOCATION = "asia-southeast1"
_DEFAULT_MODEL = "chirp_3"
_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_REQUEST_TIMEOUT = 30.0
# Google streaming gRPC limit per message; stay under 25 KB.
_STREAM_CHUNK_BYTES = 20_000

# App locale -> ordered BCP-47 codes (primary first). Chirp 3 accepts multiple
# languageCodes in one request — no separate alternativeLanguageCodes field.
_LANG_CODES: dict[str, list[str]] = {
    "bm": ["ms-MY", "en-MY", "cmn-Hans-CN"],
    "en": ["en-MY", "ms-MY", "cmn-Hans-CN"],
    "zh": ["cmn-Hans-CN", "ms-MY", "en-MY"],
}
_DEFAULT_LANG = "bm"

# Reverse map for reporting the detected language back in app terms.
_BCP47_TO_APP: dict[str, str] = {
    "ms-my": "bm",
    "en-my": "en",
    "en-us": "en",
    "en-gb": "en",
    "cmn-hans-cn": "zh",
    "zh": "zh",
    "zh-cn": "zh",
    "zh-hans": "zh",
}


class SpeechConfigError(RuntimeError):
    """Raised when Google Speech-to-Text is not configured."""


class SpeechServiceError(RuntimeError):
    """Raised when the upstream Speech API call fails."""


def _project_id() -> str:
    return os.environ.get("GOOGLE_SPEECH_PROJECT_ID", "").strip()


def _location() -> str:
    return os.environ.get("GOOGLE_SPEECH_LOCATION", _DEFAULT_LOCATION).strip() or _DEFAULT_LOCATION


def _recognize_url(project_id: str, location: str) -> str:
    host = f"{location}-speech.googleapis.com"
    return (
        f"https://{host}/v2/projects/{project_id}"
        f"/locations/{location}/recognizers/_:recognize"
    )


def _is_configured() -> bool:
    if not _project_id():
        return False
    if os.environ.get("GOOGLE_SPEECH_CREDENTIALS_JSON", "").strip():
        return True
    return bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip())


@lru_cache(maxsize=1)
def _load_credentials() -> service_account.Credentials:
    creds_json = os.environ.get("GOOGLE_SPEECH_CREDENTIALS_JSON", "").strip()
    if creds_json:
        info = json.loads(creds_json)
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=[_CLOUD_PLATFORM_SCOPE],
        )
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not creds_path:
        raise SpeechConfigError(
            "Set GOOGLE_SPEECH_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS"
        )
    return service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=[_CLOUD_PLATFORM_SCOPE],
    )


def _access_token() -> str:
    creds = _load_credentials()
    if not creds.valid:
        creds.refresh(GoogleAuthRequest())
    token = creds.token
    if not token:
        raise SpeechServiceError("Failed to obtain Google access token")
    return token


def _build_payload(audio_base64: str, language: str) -> dict[str, Any]:
    language_codes = _LANG_CODES.get(language, _LANG_CODES[_DEFAULT_LANG])
    return {
        "config": {
            "autoDecodingConfig": {},
            "languageCodes": language_codes,
            "model": _DEFAULT_MODEL,
            "features": {
                "enableAutomaticPunctuation": True,
            },
        },
        "content": audio_base64,
    }


async def _call_google(url: str, payload: dict[str, Any], token: str) -> dict[str, Any]:
    """POST to the Speech V2 API and return parsed JSON (isolated for testing)."""
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _parse_response(data: dict[str, Any], requested_language: str) -> dict[str, Any]:
    """Extract the best transcript, confidence, and detected language."""
    results = data.get("results") or []
    parts: list[str] = []
    confidence = 0.0
    detected_bcp47: str | None = None
    for result in results:
        alternatives = result.get("alternatives") or []
        if not alternatives:
            continue
        best = alternatives[0]
        parts.append(best.get("transcript", ""))
        confidence = max(confidence, float(best.get("confidence", 0.0) or 0.0))
        detected_bcp47 = detected_bcp47 or result.get("languageCode")

    transcript = " ".join(p.strip() for p in parts if p).strip()
    detected = (
        _BCP47_TO_APP.get(detected_bcp47.lower(), requested_language)
        if detected_bcp47
        else requested_language
    )
    return {
        "transcript": transcript,
        "confidence": round(confidence, 4),
        "detected_language": detected,
    }


async def transcribe(
    audio_base64: str,
    language: str = _DEFAULT_LANG,
    *,
    encoding: str = "WEBM_OPUS",  # kept for API compat; V2 uses autoDecodingConfig
    sample_rate: int = 48000,  # kept for API compat; ignored by autoDecodingConfig
) -> dict[str, Any]:
    """Transcribe base64-encoded audio via Google Speech-to-Text V2 (Chirp 3).

    Returns {transcript, confidence, detected_language}. Raises SpeechConfigError
    if credentials are not configured, or SpeechServiceError on upstream failure.
    """
    del encoding, sample_rate  # V2 auto-detects; params retained for call-site compat

    if not _is_configured():
        raise SpeechConfigError("Google Speech-to-Text is not configured")

    project_id = _project_id()
    location = _location()
    url = _recognize_url(project_id, location)
    payload = _build_payload(audio_base64, language)

    try:
        token = _access_token()
        data = await _call_google(url, payload, token)
    except SpeechConfigError:
        raise
    except httpx.HTTPStatusError as exc:
        log.warning("speech_api_http_error", status=exc.response.status_code)
        raise SpeechServiceError(f"Speech API returned {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        log.warning("speech_api_request_error", error=str(exc))
        raise SpeechServiceError("Speech API request failed") from exc
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        log.warning("speech_auth_error", error=str(exc))
        raise SpeechServiceError("Speech authentication failed") from exc

    result = _parse_response(data, language)
    log.info(
        "speech_transcribed",
        chars=len(result["transcript"]),
        detected_language=result["detected_language"],
        confidence=result["confidence"],
        model=_DEFAULT_MODEL,
        location=location,
    )
    return result


def _stream_recognize_sync(
    audio_bytes: bytes,
    language: str,
) -> list[dict[str, Any]]:
    """Run gRPC StreamingRecognize and collect interim/final events."""
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech

    project_id = _project_id()
    location = _location()
    api_endpoint = f"{location}-speech.googleapis.com"
    language_codes = _LANG_CODES.get(language, _LANG_CODES[_DEFAULT_LANG])

    client = SpeechClient(
        credentials=_load_credentials(),
        client_options={"api_endpoint": api_endpoint},
    )
    recognizer = f"projects/{project_id}/locations/{location}/recognizers/_"
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=language_codes,
        model=_DEFAULT_MODEL,
        features=cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
        ),
    )
    streaming_config = cloud_speech.StreamingRecognitionConfig(
        config=config,
        streaming_features=cloud_speech.StreamingRecognitionFeatures(
            interim_results=True,
        ),
    )

    def requests() -> Any:
        yield cloud_speech.StreamingRecognizeRequest(
            recognizer=recognizer,
            streaming_config=streaming_config,
        )
        for start in range(0, len(audio_bytes), _STREAM_CHUNK_BYTES):
            yield cloud_speech.StreamingRecognizeRequest(
                audio=audio_bytes[start : start + _STREAM_CHUNK_BYTES],
            )

    events: list[dict[str, Any]] = []
    for response in client.streaming_recognize(requests=requests()):
        if not response.results:
            continue
        for result in response.results:
            if not result.alternatives:
                continue
            alt = result.alternatives[0]
            detected_bcp47 = result.language_code or None
            detected = (
                _BCP47_TO_APP.get(detected_bcp47.lower(), language)
                if detected_bcp47
                else language
            )
            events.append(
                {
                    "is_final": result.is_final,
                    "transcript": alt.transcript,
                    "confidence": round(float(alt.confidence or 0.0), 4),
                    "detected_language": detected,
                }
            )
    return events


async def transcribe_stream(
    audio_base64: str,
    language: str = _DEFAULT_LANG,
) -> AsyncIterator[dict[str, Any]]:
    """Yield interim and final transcription events via gRPC streaming.

    Each event: {is_final, transcript, confidence, detected_language}.
    """
    if not _is_configured():
        raise SpeechConfigError("Google Speech-to-Text is not configured")

    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise SpeechServiceError("Invalid base64 audio") from exc

    try:
        events = await asyncio.to_thread(_stream_recognize_sync, audio_bytes, language)
    except ImportError as exc:
        log.warning("speech_streaming_unavailable", error=str(exc))
        raise SpeechServiceError("Streaming transcription is not available") from exc
    except Exception as exc:
        log.warning("speech_stream_error", error=str(exc))
        raise SpeechServiceError("Streaming transcription failed") from exc

    for event in events:
        yield event

    log.info(
        "speech_stream_completed",
        events=len(events),
        model=_DEFAULT_MODEL,
        location=_location(),
    )
