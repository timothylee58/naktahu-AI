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


@pytest.mark.asyncio
async def test_upcoming_source_is_reported_not_fetched(monkeypatch, capsys):
    from datetime import date

    upcoming = Source(
        name="soon", url="https://belanjawan.mof.gov.my/pdf/x.pdf", kind="pdf", domain="finance",
        ministry="MOF", language="bm", notes="n", available_from=date(2099, 1, 1),
    )
    head = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "head", head)

    ok = await check_sources((upcoming,))

    assert ok is True
    head.assert_not_called()
    assert "UPCOMING" in capsys.readouterr().out


def test_scheduled_sources_exclude_known_broken_and_every_one_has_a_reason():
    from scripts.sources import SOURCES, scheduled_sources

    broken = [s for s in SOURCES if s.known_broken]
    assert broken
    assert all(len(s.known_broken or "") > 20 for s in broken)
    assert not {s.name for s in broken} & {s.name for s in scheduled_sources()}


@pytest.mark.asyncio
async def test_check_sources_skips_known_broken_without_calling_them(monkeypatch, capsys):
    calls: list[str] = []

    async def fake_head(self, url, **kw):
        calls.append(url)
        return httpx.Response(200)

    monkeypatch.setattr(httpx.AsyncClient, "head", fake_head)
    broken = Source(name="b", url="https://b.example.gov.my/", kind="html", domain="business",
                    ministry="m", language="en", notes="n", known_broken="host blocks the runner for good")
    assert await check_sources((broken,)) is True
    assert calls == []
    assert "KNOWN BROKEN" in capsys.readouterr().out
