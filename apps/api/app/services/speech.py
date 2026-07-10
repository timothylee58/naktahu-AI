"""Google Cloud Speech-to-Text V2 (Chirp 3) wrapper for server-side voice input.

A cross-browser fallback for the browser Web Speech API (Chromium/Safari only):
the frontend records mic audio with MediaRecorder (WEBM/Opus), base64-encodes it,
and posts it to /api/v1/transcribe, which calls this service.

Uses the **V2 API + Chirp 3** model, over a **regional** recognizer endpoint
(default asia-southeast1 / Singapore) for data residency — important for a
Malaysian public-service assistant. Key points:
- V2 takes base64 audio at the top-level `content` field and an
  `autoDecodingConfig` (Chirp 3 detects the WEBM/Opus container itself, so no
  explicit encoding / sampleRate needed).
- `languageCodes` (a list) drives multilingual detection across BM/EN/ZH — one
  request handles code-switching, unlike the per-locale Web Speech path.
- Auth is a service-account OAuth token (V2 does not accept an API key): either
  `GOOGLE_SPEECH_ACCESS_TOKEN` (a pre-minted bearer token) or Application
  Default Credentials via the optional `google-auth` package.
- Degrades gracefully: without a project or credentials it raises
  SpeechConfigError so the API keeps booting and the client hides the mic.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx
import structlog

log = structlog.get_logger(__name__)

# Singapore region — keeps audio in-region for data residency.
_DEFAULT_LOCATION = "asia-southeast1"
_MODEL = "chirp_3"
_REQUEST_TIMEOUT = 30.0
_OAUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# App locale -> ordered BCP-47 languageCodes (primary first). Chirp 3 detects
# the spoken language across the list, so this covers BM/EN/ZH code-switching.
_LANG_CODES: dict[str, list[str]] = {
    "bm": ["ms-MY", "en-MY", "cmn-Hans-CN"],
    "en": ["en-MY", "ms-MY", "cmn-Hans-CN"],
    "zh": ["cmn-Hans-CN", "ms-MY", "en-MY"],
}
_DEFAULT_LANG = "bm"

# Map the detected BCP-47 tag back to app locale terms.
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
    """Raised when Speech-to-Text is not configured (no project/credentials)."""


class SpeechServiceError(RuntimeError):
    """Raised when the upstream Speech API call fails."""


def _recognizer_endpoint(location: str, project: str, recognizer: str = "_") -> str:
    """Regional V2 recognizer URL. The `_` recognizer takes inline config."""
    return (
        f"https://{location}-speech.googleapis.com/v2/projects/{project}"
        f"/locations/{location}/recognizers/{recognizer}:recognize"
    )


def _build_payload(audio_base64: str, language: str) -> dict[str, Any]:
    return {
        "config": {
            # Let Chirp 3 detect the WEBM/Opus container (no encoding/rate needed).
            "autoDecodingConfig": {},
            "model": _MODEL,
            "languageCodes": _LANG_CODES.get(language, _LANG_CODES[_DEFAULT_LANG]),
            "features": {"enableAutomaticPunctuation": True},
        },
        "content": audio_base64,
    }


def _get_access_token() -> Optional[str]:
    """Bearer token for the V2 API: explicit env token, else ADC (google-auth)."""
    token = os.environ.get("GOOGLE_SPEECH_ACCESS_TOKEN", "").strip()
    if token:
        return token
    try:  # optional — only needed when minting a token from a service account
        import google.auth
        from google.auth.transport.requests import Request

        creds, _ = google.auth.default(scopes=[_OAUTH_SCOPE])
        creds.refresh(Request())
        return creds.token
    except Exception as exc:  # noqa: BLE001 - absence/failure → treat as unconfigured
        log.warning("speech_adc_unavailable", error=str(exc))
        return None


async def _call_google(url: str, payload: dict[str, Any], token: str) -> dict[str, Any]:
    """POST to the V2 recognizer and return parsed JSON (isolated for testing)."""
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.json()


def _parse_response(data: dict[str, Any], requested_language: str) -> dict[str, Any]:
    """Extract the best transcript, confidence, and detected language."""
    results = data.get("results") or []
    parts: list[str] = []
    confidence = 0.0
    detected_bcp47: Optional[str] = None
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


async def transcribe(audio_base64: str, language: str = _DEFAULT_LANG) -> dict[str, Any]:
    """Transcribe base64 audio via Speech-to-Text V2 (Chirp 3).

    Returns {transcript, confidence, detected_language}. Raises SpeechConfigError
    when unconfigured, or SpeechServiceError on an upstream failure.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if not project:
        raise SpeechConfigError("GOOGLE_CLOUD_PROJECT is not set")

    token = _get_access_token()
    if not token:
        raise SpeechConfigError("No Speech credentials (set GOOGLE_SPEECH_ACCESS_TOKEN or ADC)")

    location = os.environ.get("GOOGLE_SPEECH_LOCATION", _DEFAULT_LOCATION).strip() or _DEFAULT_LOCATION
    url = _recognizer_endpoint(location, project)
    payload = _build_payload(audio_base64, language)

    try:
        data = await _call_google(url, payload, token)
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
        location=location,
    )
    return result
