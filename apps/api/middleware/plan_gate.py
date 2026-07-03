"""Plan and credit gating for Pro/Business-only and credit-metered endpoints.

Plan comes from the JWT app_metadata claim (services.auth.UserContext.plan),
which Supabase sets via the admin API on checkout completion — see
services/billing.py. Credits are checked against the agent_credits table.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from services.auth import UserContext, get_current_user
from services.billing import get_credits_remaining

# Ordinal rank for "at least this plan" checks. Not a strict feature
# hierarchy — student is a parallel paid tier, not a subset of pro — but
# ranking it above free is correct for the only gates Part 1 needs
# (history, voice, PDF export).
_PLAN_RANK = {"free": 0, "student": 1, "pro": 2, "business": 3}


def get_plan(user: UserContext | None) -> str:
    if not user:
        return "free"
    return user.plan


def require_plan(min_plan: str):
    """FastAPI dependency — 403s if the user's plan ranks below min_plan."""

    async def _dep(
        user: Annotated[UserContext, Depends(get_current_user)],
    ) -> UserContext:
        if _PLAN_RANK.get(user.plan, 0) < _PLAN_RANK.get(min_plan, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires the {min_plan} plan or higher.",
            )
        return user

    return _dep


def require_credits(n: int):
    """FastAPI dependency — 402s if the user has fewer than n agent credits."""

    async def _dep(
        request: Request,
        user: Annotated[UserContext, Depends(get_current_user)],
    ) -> UserContext:
        remaining = await get_credits_remaining(request.app.state.supabase, user.user_id)
        if remaining < n:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient agent credits. Top up to continue.",
            )
        return user

    return _dep
