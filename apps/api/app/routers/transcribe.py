"""POST /api/v1/transcribe — server-side voice transcription (Google Speech).

Cross-browser fallback for the browser Web Speech API. The frontend records mic
audio (WEBM/Opus via MediaRecorder), base64-encodes it, and posts it here.
"""
from __future__ import annotations

from typing import Literal, Optional

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.routers.query import _extract_user_id
from app.services.speech import (
    SpeechConfigError,
    SpeechServiceError,
    transcribe as transcribe_audio,
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
