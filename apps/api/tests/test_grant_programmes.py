"""Tests for app.services.grant_programmes and grant_finder's structured-fact enrichment."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.grant_finder.nodes import _enrich_with_structured_facts, _format_amount
from app.services.grant_programmes import get_grant_programmes_by_urls


# ── get_grant_programmes_by_urls ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_grant_programmes_by_urls_empty_input_returns_empty() -> None:
    assert await get_grant_programmes_by_urls([]) == {}
    assert await get_grant_programmes_by_urls([""]) == {}


@pytest.mark.asyncio
async def test_get_grant_programmes_by_urls_missing_env_degrades_to_empty(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    result = await get_grant_programmes_by_urls(["https://example.gov.my/grant"])
    assert result == {}


@pytest.mark.asyncio
async def test_get_grant_programmes_by_urls_keys_by_source_url(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    row = {"source_url": "https://mosti.gov.my/grant-a", "name": "Grant A", "grant_amount_myr": 50000}
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[row])
    )

    with patch("app.services.grant_programmes.acreate_client", new=AsyncMock(return_value=mock_client)):
        result = await get_grant_programmes_by_urls(["https://mosti.gov.my/grant-a", "https://other.gov.my/x"])

    assert result == {"https://mosti.gov.my/grant-a": row}


# ── _format_amount ───────────────────────────────────────────────────────────


def test_format_amount_none_returns_none() -> None:
    assert _format_amount({}) is None
    assert _format_amount({"grant_amount_myr": None}) is None


def test_format_amount_whole_number_no_decimals() -> None:
    assert _format_amount({"grant_amount_myr": 50000}) == "Up to RM50,000"


def test_format_amount_fractional_keeps_decimals() -> None:
    assert _format_amount({"grant_amount_myr": 12500.50}) == "Up to RM12,500.50"


# ── _enrich_with_structured_facts ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_no_programmes_returns_grants_unchanged() -> None:
    grants = [{"name": "Scheme A", "url": "https://x.gov.my/a", "amount_hint": "Varies"}]
    with patch(
        "app.agents.grant_finder.nodes.get_grant_programmes_by_urls",
        new=AsyncMock(return_value={}),
    ):
        result = await _enrich_with_structured_facts(grants)
    assert result == grants


@pytest.mark.asyncio
async def test_enrich_overlays_real_amount_and_deadline() -> None:
    grants = [{"name": "Scheme A", "url": "https://mosti.gov.my/a", "amount_hint": "Varies", "deadline_hint": "Check agency website"}]
    programmes = {
        "https://mosti.gov.my/a": {
            "source_url": "https://mosti.gov.my/a",
            "grant_amount_myr": 100000,
            "application_deadline": "2026-12-31",
            "eligible_sectors": ["manufacturing", "technology"],
            "bumiputera_requirement": True,
            "company_age_min_months": 12,
        }
    }
    with patch(
        "app.agents.grant_finder.nodes.get_grant_programmes_by_urls",
        new=AsyncMock(return_value=programmes),
    ):
        result = await _enrich_with_structured_facts(grants)

    enriched = result[0]
    assert enriched["amount_hint"] == "Up to RM100,000"
    assert enriched["amount_myr"] == 100000
    assert enriched["deadline_hint"] == "2026-12-31"
    assert enriched["deadline"] == "2026-12-31"
    assert enriched["eligible_sectors"] == ["manufacturing", "technology"]
    assert enriched["bumiputera_requirement"] is True
    assert enriched["company_age_min_months"] == 12
    assert enriched["is_verified"] is True


@pytest.mark.asyncio
async def test_enrich_never_fabricates_a_match_for_unknown_url() -> None:
    grants = [
        {"name": "Known", "url": "https://mosti.gov.my/a", "amount_hint": "Varies"},
        {"name": "Unknown", "url": "https://not-in-db.gov.my/z", "amount_hint": "Varies"},
    ]
    programmes = {"https://mosti.gov.my/a": {"source_url": "https://mosti.gov.my/a", "grant_amount_myr": 5000}}
    with patch(
        "app.agents.grant_finder.nodes.get_grant_programmes_by_urls",
        new=AsyncMock(return_value=programmes),
    ):
        result = await _enrich_with_structured_facts(grants)

    known, unknown = result
    assert known["is_verified"] is True
    assert "is_verified" not in unknown
    assert unknown["amount_hint"] == "Varies"


@pytest.mark.asyncio
async def test_enrich_partial_facts_only_overlays_present_fields() -> None:
    """A programme row with only some fields populated (e.g. amount known,
    deadline not yet sourced) must not clobber amount_hint with a None."""
    grants = [{"name": "Scheme A", "url": "https://mosti.gov.my/a", "amount_hint": "Varies", "deadline_hint": "Check agency website"}]
    programmes = {
        "https://mosti.gov.my/a": {
            "source_url": "https://mosti.gov.my/a",
            "grant_amount_myr": 25000,
            "application_deadline": None,
            "eligible_sectors": [],
            "bumiputera_requirement": None,
            "company_age_min_months": None,
        }
    }
    with patch(
        "app.agents.grant_finder.nodes.get_grant_programmes_by_urls",
        new=AsyncMock(return_value=programmes),
    ):
        result = await _enrich_with_structured_facts(grants)

    enriched = result[0]
    assert enriched["amount_hint"] == "Up to RM25,000"
    assert enriched["deadline_hint"] == "Check agency website"  # unchanged — no real deadline yet
    assert "bumiputera_requirement" not in enriched
