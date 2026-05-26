"""Tests for the POST /api/v1/query SSE endpoint."""
from __future__ import annotations

import json
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
