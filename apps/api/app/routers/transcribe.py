"""POST /api/v1/transcribe — server-side voice transcription (Google Speech V2).

Cross-browser fallback for the browser Web Speech API. The frontend records mic
audio (WEBM/Opus via MediaRecorder), base64-encodes it, and posts it here.

Optional: POST /api/v1/transcribe/stream returns SSE interim/final events via
Chirp 3 gRPC streaming. The default /transcribe contract is unchanged.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Literal, Optional

import structlog
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.routers.query import _extract_user_id
from app.services.speech import (
    SpeechConfigError,
    SpeechServiceError,
    transcribe as transcribe_audio,
    transcribe_stream,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["transcribe"])

# ~9 MB of base64 ≈ ~6.7 MB of audio — safely under Google's 10 MB inline sync
# limit (≈60 s of Opus is well under 1 MB, so this is a generous guard).
_MAX_AUDIO_B64_CHARS = 9_000_000


class TranscribeRequest(BaseModel):
    audio_base64: str = Field(..., min_length=16, max_length=_MAX_AUDIO_B64_CHARS)
    language: Literal["bm", "en", "zh"] = "bm"


class TranscribeResponse(BaseModel):
    transcript: str
    detected_language: str
    confidence: float


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_events(body: TranscribeRequest) -> AsyncIterator[str]:
    try:
        async for event in transcribe_stream(body.audio_base64, body.language):
            event_name = "final" if event["is_final"] else "interim"
            payload: dict[str, object] = {
                "text": event["transcript"],
                "confidence": event["confidence"],
                "detected_language": event["detected_language"],
            }
            yield _sse(event_name, payload)
        yield _sse("done", {})
    except SpeechConfigError:
        yield _sse("error", {"message": "Voice transcription is not available."})
    except SpeechServiceError as exc:
        yield _sse("error", {"message": str(exc) or "Transcription failed. Please try again."})


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_endpoint(
    body: TranscribeRequest,
    authorization: Optional[str] = Header(default=None),
) -> TranscribeResponse:
    user_id = _extract_user_id(authorization)
    log.info("transcribe_received", user_id=user_id, language=body.language, b64_len=len(body.audio_base64))

    try:
        result = await transcribe_audio(body.audio_base64, body.language)
    except SpeechConfigError as exc:
        # Not configured — surface as unavailable so the client can fall back
        # (e.g. hide the mic) rather than treating it as a client error.
        raise HTTPException(status_code=503, detail="Voice transcription is not available.") from exc
    except SpeechServiceError as exc:
        raise HTTPException(status_code=502, detail="Transcription failed. Please try again.") from exc

    return TranscribeResponse(**result)


@router.post("/transcribe/stream")
async def transcribe_stream_endpoint(
    body: TranscribeRequest,
    authorization: Optional[str] = Header(default=None),
) -> StreamingResponse:
    """Optional SSE stream with interim Chirp 3 results.

    Events: interim, final, done, error — same shape as the query SSE contract.
  """
    user_id = _extract_user_id(authorization)
    log.info(
        "transcribe_stream_received",
        user_id=user_id,
        language=body.language,
        b64_len=len(body.audio_base64),
    )
    return StreamingResponse(
        _stream_events(body),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
