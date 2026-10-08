"""Nemotron model split for the Eligibility Agent (flag-gated, this agent only).

Two roles, two models, both through the OpenAI SDK against an OpenAI-compatible
endpoint (Nebius Token Factory):

  fast       a small model for profile-field extraction at intake
  reasoning  a larger model for the streamed eligibility summary

The eligibility DECISIONS (matching, near-misses, stacking, deadline checks) are
deterministic code and never call an LLM, so the "reasoning" model only writes
the summary. That is why a mid-size model is the recommended choice for it.

Rules this module enforces:
  * Off unless ELIGIBILITY_USE_NEMOTRON is true AND a key AND that role's model
    ID are set. Off means the agent behaves exactly as before.
  * Never raises into the agent for the fast role (returns "" so the caller falls
    back); the reasoning stream raises only BEFORE its first token so the caller
    can fall back cleanly, and stops quietly after.
  * Reasoning text never reaches users: inline <think>...</think> blocks are
    stripped (including when a tag is split across streamed chunks); a separate
    ``reasoning_content`` field is never read.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, AsyncGenerator, Optional

import structlog
from openai import AsyncOpenAI

from core.config import settings

log = structlog.get_logger(__name__)

_TIMEOUT_S = 60.0   # also bounds the gap before the first streamed chunk (thinking phase)
_OPEN, _CLOSE = "<think>", "</think>"


def _usable() -> bool:
    return bool(settings.eligibility_use_nemotron and settings.nemotron_api_key)


def fast_enabled() -> bool:
    return _usable() and bool(settings.nemotron_fast_model)


def reasoning_enabled() -> bool:
    return _usable() and bool(settings.nemotron_reasoning_model)


@lru_cache(maxsize=4)
def _client_for(api_key: str, base_url: str) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=_TIMEOUT_S, max_retries=1)


def _client() -> AsyncOpenAI:
    return _client_for(settings.nemotron_api_key, settings.nemotron_base_url)


def _extra_body() -> Optional[dict[str, Any]]:
    raw = (settings.nemotron_extra_body or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("nemotron_extra_body_invalid_json")
        return None
    return parsed if isinstance(parsed, dict) else None


def strip_think(text: str) -> str:
    """Remove complete <think>...</think> blocks; an unclosed block drops the rest."""
    out, rest = [], text
    while True:
        start = rest.find(_OPEN)
        if start < 0:
            out.append(rest)
            break
        out.append(rest[:start])
        end = rest.find(_CLOSE, start)
        if end < 0:
            break
        rest = rest[end + len(_CLOSE):]
    return "".join(out).strip()


class ThinkStripper:
    """Incremental strip_think for a token stream. Holds back a trailing fragment
    that could be the start of a tag, so a tag split across chunks is still caught."""

    def __init__(self) -> None:
        self._buf = ""
        self._inside = False

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while True:
            tag = _CLOSE if self._inside else _OPEN
            idx = self._buf.find(tag)
            if idx >= 0:
                if not self._inside:
                    out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(tag):]
                self._inside = not self._inside
                continue
            # no complete tag: keep only a possible partial tag at the end
            keep = 0
            for n in range(min(len(tag) - 1, len(self._buf)), 0, -1):
                if tag.startswith(self._buf[-n:]):
                    keep = n
                    break
            emit_to = len(self._buf) - keep
            if not self._inside:
                out.append(self._buf[:emit_to])
            self._buf = self._buf[emit_to:]
            break
        return "".join(out)

    def flush(self) -> str:
        tail = "" if self._inside else self._buf
        self._buf = ""
        return tail


async def fast_complete(system: str, user: str, *, max_tokens: int = 300) -> str:
    """One non-streaming call on the fast model. Returns "" on any failure or when
    disabled, so the caller falls back to its existing provider."""
    if not fast_enabled():
        return ""
    kwargs: dict[str, Any] = {}
    if (extra := _extra_body()) is not None:
        kwargs["extra_body"] = extra
    try:
        resp = await _client().chat.completions.create(
            model=settings.nemotron_fast_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=0.2,
            **kwargs,
        )
        return strip_think(resp.choices[0].message.content or "")
    except Exception as exc:
        log.warning("nemotron_fast_failed", error=type(exc).__name__)
        return ""


async def stream_reasoning(prompt: str, system_prompt: str, *, max_tokens: int = 700) -> AsyncGenerator[str, None]:
    """Stream the summary from the reasoning model. Raises before the first token if
    the call cannot start; after that, an error ends the stream without raising so
    the caller never appends a second answer to a partial one."""
    kwargs: dict[str, Any] = {}
    if (extra := _extra_body()) is not None:
        kwargs["extra_body"] = extra
    stream = await _client().chat.completions.create(
        model=settings.nemotron_reasoning_model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        stream=True,
        max_tokens=max_tokens,
        **kwargs,
    )
    stripper = ThinkStripper()
    started = False
    try:
        async for chunk in stream:
            if not chunk.choices:
                continue
            visible = stripper.feed(chunk.choices[0].delta.content or "")
            if visible:
                started = True
                yield visible
        tail = stripper.flush()
        if tail:
            yield tail
    except Exception as exc:
        if not started:
            raise
        log.warning("nemotron_stream_interrupted", error=type(exc).__name__)
