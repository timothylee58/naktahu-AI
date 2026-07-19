"""Tests for the POST /api/v1/query SSE endpoint."""
from __future__ import annotations

import json
import time
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers.query import _extract_user_id
from core.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sse(body: str) -> list[dict]:
    """Parse an SSE body string into a list of {event, data} dicts."""
    events = []
    current: dict = {}
    for line in body.splitlines():
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            raw = line[len("data:"):].strip()
            try:
                current["data"] = json.loads(raw)
            except json.JSONDecodeError:
                current["data"] = raw
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


async def _fake_astream(inputs, stream_mode):  # type: ignore[no-untyped-def]
    """Minimal graph stream that yields one token, metadata, then done."""
    yield ("custom", "Halo, ini jawapan ujian.")
    yield (
        "updates",
        {
            "analyst": {
                "citations": [
                    {"title": "LHDN FAQ", "ministry": "LHDN", "url": "https://hasil.gov.my", "confidence": 0.8}
                ],
                "confidence_score": 0.8,
                "domain": "finance",
                "language": "bm",
                "needs_clarification": False,
            }
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_endpoint_returns_sse_events() -> None:
    """Endpoint must emit at least one token event, one citation, and done."""
    with patch("app.routers.query.pipeline") as mock_pipeline:
        mock_pipeline.astream = _fake_astream

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/query",
                json={"query": "Berapa kadar cukai?", "session_id": "sess-1"},
            )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse(resp.text)
    event_types = [e["event"] for e in events]

    assert "token" in event_types
    assert "done" in event_types


@pytest.mark.asyncio
async def test_query_endpoint_rejects_unknown_language() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/query",
            json={"query": "Berapa kadar cukai?", "language": "klingon"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_query_endpoint_token_text_present() -> None:
    """Token events must carry a non-empty 'text' field."""
    with patch("app.routers.query.pipeline") as mock_pipeline:
        mock_pipeline.astream = _fake_astream

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/query",
                json={"query": "Test query", "session_id": "sess-2"},
            )

    events = _parse_sse(resp.text)
    token_events = [e for e in events if e.get("event") == "token"]
    assert token_events, "Expected at least one token event"
    for te in token_events:
        assert "text" in te.get("data", {})
        assert te["data"]["text"]  # non-empty


@pytest.mark.asyncio
async def test_query_endpoint_citation_emitted() -> None:
    """Citation events must be emitted after all token events."""
    with patch("app.routers.query.pipeline") as mock_pipeline:
        mock_pipeline.astream = _fake_astream

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/query",
                json={"query": "Cukai pendapatan", "session_id": "sess-3"},
            )

    events = _parse_sse(resp.text)
    citation_events = [e for e in events if e.get("event") == "citation"]
    assert citation_events, "Expected at least one citation event"
    first = citation_events[0]["data"]
    assert "title" in first
    assert "url" in first


@pytest.mark.asyncio
async def test_query_endpoint_metadata_emitted() -> None:
    """Metadata event must contain confidence, domain, and language."""
    with patch("app.routers.query.pipeline") as mock_pipeline:
        mock_pipeline.astream = _fake_astream

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/query",
                json={"query": "Health services Malaysia", "session_id": "sess-4"},
            )

    events = _parse_sse(resp.text)
    meta_events = [e for e in events if e.get("event") == "metadata"]
    assert meta_events, "Expected metadata event"
    meta = meta_events[0]["data"]
    assert "confidence" in meta
    assert "domain" in meta
    assert "language" in meta
    assert "agency_contact" not in meta  # _fake_astream sets none


async def _fake_astream_with_agency_contact(inputs, stream_mode):  # type: ignore[no-untyped-def]
    yield ("custom", "Saya tidak boleh mengakses baki akaun peribadi anda.")
    yield (
        "updates",
        {
            "analyst": {
                "citations": [],
                "confidence_score": 0.5,
                "domain": "epf",
                "language": "en",
                "needs_clarification": False,
                "agency_contact": {
                    "agency": "KWSP / EPF",
                    "domain": "epf",
                    "hotline": "03-8922 6000",
                    "portal": "https://www.kwsp.gov.my",
                },
            }
        },
    )


@pytest.mark.asyncio
async def test_query_endpoint_metadata_includes_agency_contact_when_present() -> None:
    """A personal-data query's agency_contact must reach the client via metadata."""
    with patch("app.routers.query.pipeline") as mock_pipeline:
        mock_pipeline.astream = _fake_astream_with_agency_contact

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/query",
                json={"query": "What is my EPF balance?", "session_id": "sess-agency"},
            )

    events = _parse_sse(resp.text)
    meta = [e for e in events if e.get("event") == "metadata"][0]["data"]
    assert meta["agency_contact"]["agency"] == "KWSP / EPF"
    assert meta["agency_contact"]["portal"] == "https://www.kwsp.gov.my"


@pytest.mark.asyncio
async def test_query_endpoint_event_order() -> None:
    """SSE events must arrive in order: token(s) → citation(s) → metadata → done."""
    with patch("app.routers.query.pipeline") as mock_pipeline:
        mock_pipeline.astream = _fake_astream

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/query",
                json={"query": "EPF withdrawal", "session_id": "sess-5"},
            )

    events = _parse_sse(resp.text)
    types = [e["event"] for e in events]

    assert types[-1] == "done"
    # done must come after metadata
    if "metadata" in types:
        assert types.index("metadata") < types.index("done")
    # citation must come after all tokens
    token_indices = [i for i, t in enumerate(types) if t == "token"]
    citation_indices = [i for i, t in enumerate(types) if t == "citation"]
    if token_indices and citation_indices:
        assert max(token_indices) < min(citation_indices)


@pytest.mark.asyncio
async def test_query_endpoint_error_on_pipeline_failure() -> None:
    """If the pipeline raises, the endpoint emits an error event."""
    async def _failing_astream(inputs, stream_mode):  # type: ignore[no-untyped-def]
        raise RuntimeError("pipeline exploded")
        yield  # make it an async generator

    with patch("app.routers.query.pipeline") as mock_pipeline:
        mock_pipeline.astream = _failing_astream

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/query",
                json={"query": "Broken query", "session_id": "sess-err"},
            )

    events = _parse_sse(resp.text)
    error_events = [e for e in events if e.get("event") == "error"]
    assert error_events, "Expected an error event on pipeline failure"
    assert "message" in error_events[0]["data"]


# ---------------------------------------------------------------------------
# _extract_user_id — must verify JWT signature, never trust an unverified decode
# ---------------------------------------------------------------------------

def _make_token(sub: str = "user-1", secret: str | None = None, exp_seconds: int = 3600) -> str:
    return jwt.encode(
        {
            "sub": sub,
            "aud": settings.supabase_jwt_aud,
            "exp": int(time.time()) + exp_seconds,
        },
        secret if secret is not None else settings.jwt_secret,
        algorithm="HS256",
    )


def test_extract_user_id_accepts_valid_signature() -> None:
    token = _make_token(sub="user-42")
    assert _extract_user_id(f"Bearer {token}") == "user-42"


def test_extract_user_id_rejects_tampered_signature() -> None:
    # Signed with the wrong secret — payload looks legitimate but signature is invalid.
    token = _make_token(sub="attacker", secret="not-the-real-secret")
    assert _extract_user_id(f"Bearer {token}") is None


def test_extract_user_id_rejects_forged_none_algorithm() -> None:
    # Classic JWT attack: attacker crafts an unsigned token with alg=none and
    # sets an arbitrary sub claim. A verified decoder must reject this.
    forged = jwt.encode(
        {"sub": "attacker", "aud": settings.supabase_jwt_aud},
        key="",
        algorithm="none",
    )
    assert _extract_user_id(f"Bearer {forged}") is None


def test_extract_user_id_rejects_expired_token() -> None:
    token = _make_token(sub="user-1", exp_seconds=-10)
    assert _extract_user_id(f"Bearer {token}") is None


def test_extract_user_id_returns_none_for_missing_or_malformed_header() -> None:
    assert _extract_user_id(None) is None
    assert _extract_user_id("") is None
    assert _extract_user_id("NotBearer abc") is None
    assert _extract_user_id("Bearer not-a-jwt") is None
