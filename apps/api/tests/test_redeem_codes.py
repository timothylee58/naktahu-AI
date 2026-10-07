"""Tests for services.redeem_codes — claim-first idempotency and both
fulfillment kinds (credits / plan_trial)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from postgrest.exceptions import APIError

from services.redeem_codes import redeem_code


def _unique_violation() -> APIError:
    return APIError({"code": "23505", "message": "duplicate key"})


class _FakeTables:
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


def _code_row(**overrides) -> dict:
    row = {
        "id": "code-1",
        "code": "SAVE20",
        "kind": "credits",
        "credits_amount": 5,
        "plan_tier": None,
        "plan_duration_days": None,
        "max_uses": None,
        "uses_count": 0,
        "expires_at": None,
        "active": True,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_redeem_code_rejects_unknown_code():
    sb, tables = _sb()
    tables["redeem_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    result = await redeem_code(sb, "NOPE", "u1")
    assert result["status"] == "invalid_code"


@pytest.mark.asyncio
async def test_redeem_code_rejects_inactive_code():
    sb, tables = _sb()
    tables["redeem_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_code_row(active=False)]
    )
    result = await redeem_code(sb, "SAVE20", "u1")
    assert result["status"] == "invalid_code"


@pytest.mark.asyncio
async def test_redeem_code_rejects_expired_code():
    sb, tables = _sb()
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    tables["redeem_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_code_row(expires_at=expired)]
    )
    result = await redeem_code(sb, "SAVE20", "u1")
    assert result["status"] == "expired"


@pytest.mark.asyncio
async def test_redeem_code_rejects_exhausted_code():
    sb, tables = _sb()
    tables["redeem_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_code_row(max_uses=1, uses_count=1)]
    )
    result = await redeem_code(sb, "SAVE20", "u1")
    assert result["status"] == "exhausted"


@pytest.mark.asyncio
async def test_redeem_code_rejects_duplicate_redemption_by_same_user():
    sb, tables = _sb()
    tables["redeem_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_code_row()]
    )
    tables["redeem_code_redemptions"].insert.return_value.execute.side_effect = _unique_violation()
    result = await redeem_code(sb, "SAVE20", "u1")
    assert result["status"] == "already_redeemed"


@pytest.mark.asyncio
async def test_redeem_code_grants_credits_on_happy_path():
    sb, tables = _sb()
    tables["redeem_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_code_row(credits_amount=10)]
    )
    tables["redeem_code_redemptions"].insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])
    tables["redeem_codes"].update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])

    with patch("services.redeem_codes.add_credits", AsyncMock()) as mock_add_credits:
        result = await redeem_code(sb, "SAVE20", "u1")

    assert result == {"status": "credits_granted", "credits_amount": 10}
    mock_add_credits.assert_awaited_once_with(sb, "u1", 10)


@pytest.mark.asyncio
async def test_redeem_code_grants_plan_trial_on_happy_path():
    sb, tables = _sb()
    tables["redeem_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_code_row(kind="plan_trial", credits_amount=None, plan_tier="pro", plan_duration_days=14)]
    )
    tables["redeem_code_redemptions"].insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])
    tables["redeem_codes"].update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])

    with patch("services.redeem_codes.grant_temporary_plan", AsyncMock()) as mock_grant:
        result = await redeem_code(sb, "SAVE20", "u1")

    assert result == {"status": "plan_granted", "plan_tier": "pro", "duration_days": 14}
    mock_grant.assert_awaited_once_with(
        sb, user_id="u1", plan_tier="pro", duration_days=14, source="redeem_code", source_id="code-1"
    )


@pytest.mark.asyncio
async def test_redeem_code_releases_claim_when_fulfillment_fails():
    """If add_credits/grant_temporary_plan raises after the claim-first
    insert succeeded, the redemption row must be released — otherwise the
    code becomes permanently unredeemable for this user despite never
    actually granting anything."""
    sb, tables = _sb()
    tables["redeem_codes"].select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[_code_row()]
    )
    tables["redeem_code_redemptions"].insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])

    with patch("services.redeem_codes.add_credits", AsyncMock(side_effect=RuntimeError("db down"))):
        with pytest.raises(RuntimeError):
            await redeem_code(sb, "SAVE20", "u1")

    tables["redeem_code_redemptions"].delete.return_value.eq.return_value.eq.return_value.execute.assert_called_once()
