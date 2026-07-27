"""Plan and credit gating for Pro/Business-only and credit-metered endpoints.

Plan comes from the JWT app_metadata claim (services.auth.UserContext.plan),
which Supabase sets via the admin API on checkout completion — see
services/billing.py. Credits are checked against the agent_credits table.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from services.auth import VALID_ENTITLEMENTS, UserContext, get_current_user
from services.billing import get_credits_remaining

# Ordinal rank for "at least this plan" checks. Not a strict feature
# hierarchy — student is a parallel paid tier, not a subset of pro — but
# ranking it above free is correct for the only gates Part 1 needs
# (history, voice, PDF export).
#
# "investor" is deliberately ABSENT from this table, and must stay absent.
# It follows the same reasoning as student, one step further: the investor
# plan (Investor Intelligence — thesis-vs-grant matching for VCs/angels) is
# a different market SEGMENT, not a bigger version of business. Adding it as
# a rung would produce two wrong answers at once — a business-plan SME
# (an enterprise customer) would auto-inherit investor intelligence, and an
# investor-plan VC firm would auto-inherit every pro/business SME feature.
# Gate it with require_entitlement("investor") instead, which is an explicit
# membership test rather than an ordinal comparison. Anything else that is a
# parallel market segment rather than "more of the same product" belongs in
# VALID_ENTITLEMENTS (services/auth.py), not here.
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


def has_entitlement(user: UserContext | None, entitlement: str) -> bool:
    """True if `user` explicitly holds `entitlement`.

    Membership test only — never an ordinal comparison against _PLAN_RANK.
    No plan implies an entitlement it does not literally name.
    """
    if not user:
        return False
    return entitlement in (user.entitlements or ())


def require_entitlement(entitlement: str):
    """FastAPI dependency — 403s unless the user explicitly holds `entitlement`.

    Sits ALONGSIDE require_plan/require_credits rather than inside the plan
    ladder. Anonymous callers get 401 (from get_current_user); authenticated
    users without the entitlement get 403 — matching require_plan's shape.
    """
    if entitlement not in VALID_ENTITLEMENTS:
        raise ValueError(f"Unknown entitlement: {entitlement}")

    async def _dep(
        user: Annotated[UserContext, Depends(get_current_user)],
    ) -> UserContext:
        if not has_entitlement(user, entitlement):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This feature requires the {entitlement} plan. "
                    "It is a separate subscription, not an upgrade of your current plan."
                ),
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
