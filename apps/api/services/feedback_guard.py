"""Feedback verifier — the gate every user-submitted feedback payload and
screenshot passes before it is stored.

Feedback is untrusted input that ends up in places a human or a pipeline
reads later: the Supabase table editor (stored XSS), and
scripts/mine_feedback_gaps.py, which turns negative feedback into eval
candidates (prompt injection). It is also a cheap flood target. So this module
does three jobs, all deterministic (no LLM call — a model-based verifier would
itself be a prompt-injection surface and add latency to a form submit):

1. verify_text   — injection / markup / spam verdict: accept, flag, reject.
2. verify_image  — decode, bound, and re-encode screenshots (strips EXIF).
3. enforce_*     — per-user velocity cap and duplicate suppression in Redis.
"""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, Optional

import structlog
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.middleware.sanitise import INJECTION_PATTERNS, _fold_confusables

logger = structlog.get_logger()

MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_IMAGE_SIDE = 4096
MAX_IMAGE_PIXELS = 16_000_000

SUBMISSIONS_PER_HOUR = 5
UPLOADS_PER_HOUR = 5
DUPLICATE_WINDOW_SECONDS = 24 * 3600

_ZERO_WIDTH_RE = re.compile("[​-‏‪-‮⁠-⁤﻿]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MARKUP_RE = re.compile(
    r"<\s*/?\s*(script|iframe|object|embed|img|svg|style|link|a|form)\b"
    r"|javascript\s*:|data\s*:\s*text/html|\bon[a-z]{3,}\s*=",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_REPEATED_CHAR_RE = re.compile(r"(.)\1{19,}")

_FORMATS: dict[str, tuple[str, str]] = {
    "PNG": ("image/png", "png"),
    "JPEG": ("image/jpeg", "jpg"),
    "WEBP": ("image/webp", "webp"),
}


@dataclass(frozen=True)
class TextVerdict:
    decision: Literal["accept", "flag", "reject"]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifiedImage:
    data: bytes
    content_type: str
    extension: str


class ImageRejected(Exception):
    """Raised with a short user-safe reason when an upload fails verification."""


def clean_text(text: str) -> str:
    """Strip zero-width and control characters; keeps newlines and tabs."""
    return _CONTROL_RE.sub("", _ZERO_WIDTH_RE.sub("", text)).strip()


def fingerprint(*parts: str) -> str:
    """sha256 of the normalised payload — raw text never goes in a Redis key."""
    joined = "|".join(clean_text(p).lower() for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def verify_text(*parts: Optional[str]) -> TextVerdict:
    reasons: list[str] = []
    flagged: list[str] = []
    for raw in parts:
        if not raw:
            continue
        # Same normalisation as ingestion/query scans so homoglyph and
        # zero-width evasion that fails there fails here too.
        detection = _fold_confusables(unicodedata.normalize("NFKC", clean_text(raw)))
        if any(p.search(detection) for p in INJECTION_PATTERNS):
            reasons.append("prompt_injection")
        if _MARKUP_RE.search(detection):
            reasons.append("markup")
        if len(_URL_RE.findall(detection)) > 2:
            flagged.append("link_spam")
        if _REPEATED_CHAR_RE.search(detection):
            flagged.append("repeated_characters")
        letters = sum(ch.isalpha() for ch in detection)
        if len(detection) >= 40 and letters / len(detection) < 0.3:
            flagged.append("low_text_ratio")
    if reasons:
        return TextVerdict("reject", tuple(dict.fromkeys(reasons)))
    if flagged:
        return TextVerdict("flag", tuple(dict.fromkeys(flagged)))
    return TextVerdict("accept")


def verify_image(data: bytes) -> VerifiedImage:
    if not data:
        raise ImageRejected("empty_file")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageRejected("file_too_large")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format or ""
            width, height = probe.size
        if fmt not in _FORMATS:
            raise ImageRejected("unsupported_format")
        if max(width, height) > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
            raise ImageRejected("dimensions_too_large")
        # Magic bytes decide the format, never the client's Content-Type or
        # filename. Re-encoding drops EXIF/GPS and any trailing payload.
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if fmt == "JPEG":
                img = img.convert("RGB")
            elif img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            out = io.BytesIO()
            img.save(out, format=fmt)
    except ImageRejected:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise ImageRejected("not_a_valid_image") from None
    content_type, extension = _FORMATS[fmt]
    return VerifiedImage(out.getvalue(), content_type, extension)


async def _bump(redis: Any, key: str, limit: int, ttl: int) -> bool:
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, ttl)
    return int(count) <= limit


async def enforce_rate(redis: Any, actor: str, *, kind: Literal["submit", "upload"]) -> None:
    """Hourly cap per user (or anon session) on top of the slowapi IP limit.

    Fails open when Redis is unavailable: the slowapi limiter still applies and
    blocking all feedback on a cache outage is the worse failure.
    """
    if redis is None:
        return
    limit = SUBMISSIONS_PER_HOUR if kind == "submit" else UPLOADS_PER_HOUR
    try:
        ok = await _bump(redis, f"feedback:{kind}:{actor}", limit, 3600)
    except Exception:
        logger.warning("feedback_guard_redis_unavailable", check="rate")
        return
    if not ok:
        raise HTTPException(
            status_code=429,
            detail="Too much feedback sent recently. Please try again later.",
            headers={"Retry-After": "3600"},
        )


async def enforce_unique(redis: Any, digest: str) -> None:
    """Reject the same payload resubmitted inside the duplicate window."""
    if redis is None:
        return
    try:
        fresh = await redis.set(f"feedback:dup:{digest}", "1", nx=True, ex=DUPLICATE_WINDOW_SECONDS)
    except Exception:
        logger.warning("feedback_guard_redis_unavailable", check="duplicate")
        return
    if not fresh:
        raise HTTPException(status_code=409, detail="This feedback was already received.")
