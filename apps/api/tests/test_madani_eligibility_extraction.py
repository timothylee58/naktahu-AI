"""Tests for app.services.madani_eligibility_extraction — LLM-based
eligibility_rules extraction that feeds scripts/ingest_madani.py's
needs_review decision (migration 043)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.madani_eligibility_extraction import extract_eligibility_rules


def _mock_response(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_extracts_concrete_income_cap_and_is_confident(monkeypatch):
    resp = _mock_response('{"max_household_income_myr": 5000, "states": ["selangor"]}')
    monkeypatch.setattr("app.services.madani_eligibility_extraction.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))

    rules, confident = await extract_eligibility_rules("Skim X", "Untuk isi rumah berpendapatan RM5,000 ke bawah di Selangor.")

    assert rules == {"max_household_income_myr": 5000.0, "states": ["selangor"]}
    assert confident is True


@pytest.mark.asyncio
async def test_empty_extraction_is_not_confident(monkeypatch):
    """A scheme genuinely open to all (or one the LLM just couldn't find
    constraints for) returns {} either way — confident=False in both
    cases, by design (see the module's own docstring on why these two
    cases are deliberately indistinguishable from this function alone)."""
    resp = _mock_response("{}")
    monkeypatch.setattr("app.services.madani_eligibility_extraction.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))

    rules, confident = await extract_eligibility_rules("Bantuan Am Persekutuan", "Bantuan am untuk semua rakyat Malaysia.")

    assert rules == {}
    assert confident is False


@pytest.mark.asyncio
async def test_llm_failure_degrades_to_empty_and_not_confident(monkeypatch):
    monkeypatch.setattr(
        "app.services.madani_eligibility_extraction.ilmu_client.chat.completions.create",
        AsyncMock(side_effect=RuntimeError("ILMU unavailable")),
    )

    rules, confident = await extract_eligibility_rules("Skim X", "desc")

    assert rules == {}
    assert confident is False


@pytest.mark.asyncio
async def test_drops_unrecognized_and_out_of_range_values(monkeypatch):
    resp = _mock_response(
        '{"max_household_income_myr": -500, "states": ["atlantis"], '
        '"requires_oku": "yes", "min_dependents_children": 99, '
        '"employment_status": ["astronaut", "b40"], "made_up_key": true}'
    )
    monkeypatch.setattr("app.services.madani_eligibility_extraction.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))

    rules, confident = await extract_eligibility_rules("Skim Y", "desc")

    # Negative income, unknown state, non-boolean requires_oku, an
    # out-of-range dependents count, and an unrecognized key are all
    # dropped; only the valid "b40" survives from employment_status.
    assert rules == {"employment_status": ["b40"]}
    assert confident is True


@pytest.mark.asyncio
async def test_drops_unparseable_response(monkeypatch):
    resp = _mock_response("Sorry, I could not determine eligibility from this text.")
    monkeypatch.setattr("app.services.madani_eligibility_extraction.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))

    rules, confident = await extract_eligibility_rules("Skim Z", "desc")

    assert rules == {}
    assert confident is False


@pytest.mark.asyncio
async def test_valid_boolean_requires_oku_is_kept(monkeypatch):
    resp = _mock_response('{"requires_oku": true}')
    monkeypatch.setattr("app.services.madani_eligibility_extraction.ilmu_client.chat.completions.create", AsyncMock(return_value=resp))

    rules, confident = await extract_eligibility_rules("Skim OKU", "Khas untuk penerima kad OKU.")

    assert rules == {"requires_oku": True}
    assert confident is True
