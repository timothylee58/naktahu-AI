"""Google Cloud Speech-to-Text wrapper (server-side voice transcription).

A cross-browser fallback for the browser Web Speech API (Chromium/Safari only):
the frontend records mic audio with MediaRecorder (WEBM/Opus), base64-encodes it,
and posts it to /api/v1/transcribe, which calls this service.

Uses the v1p1beta1 `speech:recognize` REST endpoint with an API key. Key notes:
- Browser MediaRecorder produces WEBM_OPUS (not LINEAR16), so that is the
  default encoding; sampleRateHertz must be 48000 for Opus.
- `alternativeLanguageCodes` lets one request detect BM/EN/ZH code-switching,
  which the per-locale Web Speech path cannot do.
- Degrades gracefully: if GOOGLE_SPEECH_API_KEY is unset, raises
  SpeechConfigError so the API keeps booting (mirrors Redis/Supabase handling).
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)

_DEFAULT_ENDPOINT = "https://speech.googleapis.com/v1p1beta1/speech:recognize"
# Opus in a WebM container is always 48 kHz.
_OPUS_SAMPLE_RATE = 48000
_REQUEST_TIMEOUT = 30.0

# App locale -> (primary BCP-47, alternative BCP-47 codes). Malaysia-tuned:
# Malay, Malaysian English, and Simplified Mandarin. `alternativeLanguageCodes`
# accepts up to 3 extras; two here covers the trilingual audience.
_LANG_MAP: dict[str, tuple[str, list[str]]] = {
    "bm": ("ms-MY", ["en-MY", "cmn-Hans-CN"]),
    "en": ("en-MY", ["ms-MY", "cmn-Hans-CN"]),
    "zh": ("cmn-Hans-CN", ["ms-MY", "en-MY"]),
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
    """Raised when Google Speech-to-Text is not configured (no API key)."""


class SpeechServiceError(RuntimeError):
    """Raised when the upstream Speech API call fails."""


def _build_payload(audio_base64: str, language: str, encoding: str, sample_rate: int) -> dict[str, Any]:
    primary, alternatives = _LANG_MAP.get(language, _LANG_MAP[_DEFAULT_LANG])
    config: dict[str, Any] = {
        "encoding": encoding,
        "languageCode": primary,
        "alternativeLanguageCodes": alternatives,
        "enableAutomaticPunctuation": True,
        # Utterance-length model — better than "default" for short dictation.
        "model": "latest_short",
    }
    # sampleRateHertz is required for Opus; harmless to include for others.
    if sample_rate:
        config["sampleRateHertz"] = sample_rate
    return {"config": config, "audio": {"content": audio_base64}}


async def _call_google(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST to the Speech API and return the parsed JSON (isolated for testing)."""
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
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
    encoding: str = "WEBM_OPUS",
    sample_rate: int = _OPUS_SAMPLE_RATE,
) -> dict[str, Any]:
    """Transcribe base64-encoded audio via Google Speech-to-Text.

    Returns {transcript, confidence, detected_language}. Raises SpeechConfigError
    if no API key is configured, or SpeechServiceError on an upstream failure.
    """
    api_key = os.environ.get("GOOGLE_SPEECH_API_KEY", "").strip()
    if not api_key:
        raise SpeechConfigError("GOOGLE_SPEECH_API_KEY is not set")

    endpoint = os.environ.get("GOOGLE_SPEECH_ENDPOINT", _DEFAULT_ENDPOINT).strip() or _DEFAULT_ENDPOINT
    url = f"{endpoint}?key={api_key}"
    payload = _build_payload(audio_base64, language, encoding, sample_rate)

    try:
        data = await _call_google(url, payload)
    except httpx.HTTPStatusError as exc:
        log.warning("speech_api_http_error", status=exc.response.status_code)
        raise SpeechServiceError(f"Speech API returned {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        log.warning("speech_api_request_error", error=str(exc))
        raise SpeechServiceError("Speech API request failed") from exc

    result = _parse_response(data, language)
    log.info(
        "speech_transcribed",
        chars=len(result["transcript"]),
        detected_language=result["detected_language"],
        confidence=result["confidence"],
    )
    return result
