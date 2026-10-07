"""Tests for services.referral — code generation, referral application and
completion, and temporary plan grants."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from services.referral import (
    apply_referral_code,
    get_active_plan_grant,
    get_or_create_referral_code,
    grant_temporary_plan,
    revert_expired_plan_grant,
)


def _unique_violation() -> APIError:
    return APIError({"code": "23505", "message": "duplicate key"})


class _FakeTables:
    """sb.table(name) returns a distinct MagicMock per table name, so a
    flow that touches multiple tables (referral_codes, referrals,
    plan_grants) can have each mocked independently without one table's
    return_value bleeding into another's."""

    def __init__(self):
        self._tables: dict[str, MagicMock] = {}

    def __call__(self, name: str) -> MagicMock:
        if name not in self._tables:
            self._tables[name] = MagicMock()
        return self._tables[name]

    def __getitem__(self, name: str) -> MagicMock:
        return self(name)


def _sb() -> tuple[MagicMock, _FakeTables]:
    tables = _FakeTables()
    sb = MagicMock()
    sb.table.side_effect = tables
    return sb, tables


@pytest.mark.asyncio
async def test_get_or_create_referral_code_returns_existing():
    sb, tables = _sb()
    tables["referral_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"code": "ABCDE"}]
    )
    code = await get_or_create_referral_code(sb, "u1")
    assert code == "ABCDE"
    tables["referral_codes"].insert.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_referral_code_creates_when_none_exists():
    sb, tables = _sb()
    tables["referral_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    tables["referral_codes"].insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])
    code = await get_or_create_referral_code(sb, "u1")
    assert len(code) == 5
    tables["referral_codes"].insert.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_referral_code_retries_on_collision():
    sb, tables = _sb()
    tables["referral_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    tables["referral_codes"].insert.return_value.execute.side_effect = [_unique_violation(), MagicMock(data=[{"id": "1"}])]
    code = await get_or_create_referral_code(sb, "u1")
    assert len(code) == 5
    assert tables["referral_codes"].insert.call_count == 2


@pytest.mark.asyncio
async def test_apply_referral_code_rejects_unknown_code():
    sb, tables = _sb()
    tables["referral_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    result = await apply_referral_code(sb, "NOPE1", "referred-user")
    assert result["status"] == "invalid_code"


@pytest.mark.asyncio
async def test_apply_referral_code_blocks_self_referral():
    sb, tables = _sb()
    tables["referral_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"user_id": "same-user"}]
    )
    result = await apply_referral_code(sb, "ABCDE", "same-user")
    assert result["status"] == "self_referral_blocked"


@pytest.mark.asyncio
async def test_apply_referral_code_rejects_already_referred_user():
    sb, tables = _sb()
    tables["referral_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"user_id": "referrer-1"}]
    )
    tables["referrals"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"referred_user_id": "referred-1"}]
    )
    result = await apply_referral_code(sb, "ABCDE", "referred-1")
    assert result["status"] == "already_referred"


@pytest.mark.asyncio
async def test_apply_referral_code_happy_path_grants_both_sides():
    sb, tables = _sb()
    tables["referral_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"user_id": "referrer-1"}]
    )
    tables["referrals"].select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    tables["referrals"].insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])
    tables["referrals"].update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])

    grants: list[tuple] = []

    async def _fake_grant(_sb, *, user_id, plan_tier, duration_days, source, source_id):
        grants.append((user_id, plan_tier, duration_days, source, source_id))
        return True

    with patch("services.referral._complete_referral", AsyncMock(side_effect=lambda sb, r, ref: None)) as mock_complete:
        result = await apply_referral_code(sb, "ABCDE", "referred-1")

    assert result["status"] == "completed"
    assert result["referrer_user_id"] == "referrer-1"
    mock_complete.assert_awaited_once_with(sb, "referrer-1", "referred-1")


@pytest.mark.asyncio
async def test_grant_temporary_plan_is_idempotent_on_duplicate_source():
    sb, tables = _sb()
    tables["plan_grants"].insert.return_value.execute.side_effect = _unique_violation()
    granted = await grant_temporary_plan(
        sb, user_id="u1", plan_tier="pro", duration_days=30, source="referral", source_id="r1"
    )
    assert granted is False


@pytest.mark.asyncio
async def test_grant_temporary_plan_does_not_downgrade_higher_plan(monkeypatch):
    sb, tables = _sb()
    sb.auth.admin.get_user_by_id.return_value = MagicMock(user=MagicMock(app_metadata={"plan": "business"}))
    tables["plan_grants"].insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])

    set_plan_mock = AsyncMock()
    monkeypatch.setattr("services.referral.set_plan", set_plan_mock)

    granted = await grant_temporary_plan(
        sb, user_id="u1", plan_tier="pro", duration_days=30, source="referral", source_id="r1"
    )
    assert granted is True
    set_plan_mock.assert_not_awaited()  # pro (rank 2) must not downgrade business (rank 3)


@pytest.mark.asyncio
async def test_grant_temporary_plan_upgrades_lower_plan(monkeypatch):
    sb, tables = _sb()
    sb.auth.admin.get_user_by_id.return_value = MagicMock(user=MagicMock(app_metadata={"plan": "free"}))
    tables["plan_grants"].insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])

    set_plan_mock = AsyncMock()
    monkeypatch.setattr("services.referral.set_plan", set_plan_mock)

    granted = await grant_temporary_plan(
        sb, user_id="u1", plan_tier="pro", duration_days=30, source="referral", source_id="r1"
    )
    assert granted is True
    set_plan_mock.assert_awaited_once_with(sb, "u1", "pro")


@pytest.mark.asyncio
async def test_get_active_plan_grant_returns_none_when_absent():
    sb, tables = _sb()
    tables["plan_grants"].select.return_value.eq.return_value.is_.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    grant = await get_active_plan_grant(sb, "u1")
    assert grant is None


@pytest.mark.asyncio
async def test_revert_expired_plan_grant_restores_previous_plan_and_marks_reverted():
    sb, tables = _sb()
    grant = {"id": "g1", "user_id": "u1", "previous_plan": "free"}
    await revert_expired_plan_grant(sb, grant)
    sb.auth.admin.update_user_by_id.assert_called_once_with("u1", {"app_metadata": {"plan": "free"}})
    tables["plan_grants"].update.assert_called_once()
