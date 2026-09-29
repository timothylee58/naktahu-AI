"""Tests for scripts/check_sources.py — the ingestion-source health check."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from scripts.check_sources import check_sources
from scripts.sources import Source

_SOURCE_A = Source(
    name="a", url="https://a.gov.my", kind="html", domain="business",
    ministry="Test", language="en", notes="",
)
_SOURCE_B = Source(
    name="b", url="https://b.gov.my", kind="html", domain="legal",
    ministry="Test", language="en", notes="",
)


def _mock_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    return resp


@pytest.mark.asyncio
async def test_check_sources_all_healthy(monkeypatch):
    async def fake_head(url, follow_redirects=True):
        return _mock_response(200)

    monkeypatch.setattr(httpx.AsyncClient, "head", AsyncMock(side_effect=fake_head))

    ok = await check_sources((_SOURCE_A, _SOURCE_B))
    assert ok is True


@pytest.mark.asyncio
async def test_check_sources_reports_4xx_as_unhealthy(monkeypatch):
    async def fake_head(url, follow_redirects=True):
        return _mock_response(200) if "a.gov.my" in url else _mock_response(404)

    monkeypatch.setattr(httpx.AsyncClient, "head", AsyncMock(side_effect=fake_head))

    ok = await check_sources((_SOURCE_A, _SOURCE_B))
    assert ok is False


@pytest.mark.asyncio
async def test_check_sources_falls_back_to_get_on_405(monkeypatch):
    async def fake_head(url, follow_redirects=True):
        return _mock_response(405)

    async def fake_get(url, follow_redirects=True):
        return _mock_response(200)

    monkeypatch.setattr(httpx.AsyncClient, "head", AsyncMock(side_effect=fake_head))
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(side_effect=fake_get))

    ok = await check_sources((_SOURCE_A,))
    assert ok is True


@pytest.mark.asyncio
async def test_check_sources_reports_connection_error_as_unhealthy(monkeypatch):
    async def fake_head(url, follow_redirects=True):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "head", AsyncMock(side_effect=fake_head))

    ok = await check_sources((_SOURCE_A,))
    assert ok is False
