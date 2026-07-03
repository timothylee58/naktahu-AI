from unittest.mock import AsyncMock

import pytest

from middleware.plan_gate import get_plan
from services.auth import UserContext


def test_get_plan_none_user_is_free():
    assert get_plan(None) == "free"


def test_get_plan_reads_user_plan():
    assert get_plan(UserContext(user_id="u1", is_anonymous=False, plan="business")) == "business"


@pytest.mark.asyncio
async def test_require_credits_dependency_blocks_when_insufficient(monkeypatch):
    from fastapi import Request

    from middleware.plan_gate import require_credits

    monkeypatch.setattr(
        "middleware.plan_gate.get_credits_remaining",
        AsyncMock(return_value=2),
    )

    dep = require_credits(5)
    user = UserContext(user_id="credit-poor", is_anonymous=False, plan="pro")
    request = Request(scope={"type": "http", "app": AsyncMock(state=AsyncMock(supabase=AsyncMock()))})

    with pytest.raises(Exception) as exc_info:
        await dep(request, user)
    assert getattr(exc_info.value, "status_code", None) == 402


@pytest.mark.asyncio
async def test_require_credits_dependency_passes_when_sufficient(monkeypatch):
    from fastapi import Request

    from middleware.plan_gate import require_credits

    monkeypatch.setattr(
        "middleware.plan_gate.get_credits_remaining",
        AsyncMock(return_value=10),
    )

    dep = require_credits(5)
    user = UserContext(user_id="credit-rich", is_anonymous=False, plan="pro")
    request = Request(scope={"type": "http", "app": AsyncMock(state=AsyncMock(supabase=AsyncMock()))})

    result = await dep(request, user)
    assert result is user
