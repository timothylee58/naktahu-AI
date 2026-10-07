"""Referral program: per-user share code, referral tracking, and the
one-time "both sides get 1 month Pro free" reward on completion.

"Completion" in this codebase means the referred user has signed up and
applied the code — there is no separate multi-step onboarding flow to gate
on (chat-based sign-in via Supabase Auth directly), so signup + code
application IS the completion event. Documented here rather than silently
assumed, since a future onboarding flow could legitimately move this.
"""
from __future__ import annotations

import asyncio
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from postgrest.exceptions import APIError
from supabase import Client

from services.billing import set_plan

log = structlog.get_logger(__name__)

_POSTGRES_UNIQUE_VIOLATION = "23505"
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 5
_REFERRAL_REWARD_PLAN = "pro"
_REFERRAL_REWARD_DAYS = 30


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


async def get_or_create_referral_code(supabase: Client, user_id: str) -> str:
    """Idempotent: returns the existing code, or claims a fresh random one.
    Collision retry (not upsert-on-conflict) since the conflict is on the
    `code` column, not `user_id` — a fresh random code is regenerated on
    collision, not silently overwriting someone else's."""

    def _fetch() -> Optional[str]:
        res = supabase.table("referral_codes").select("code").eq("user_id", user_id).execute()
        return res.data[0]["code"] if res.data else None

    existing = await asyncio.to_thread(_fetch)
    if existing:
        return existing

    for _ in range(10):
        code = _generate_code()

        def _insert(code: str = code) -> bool:
            try:
                supabase.table("referral_codes").insert({"user_id": user_id, "code": code}).execute()
                return True
            except APIError as exc:
                if exc.code == _POSTGRES_UNIQUE_VIOLATION:
                    return False
                raise

        if await asyncio.to_thread(_insert):
            return code

    raise RuntimeError("Could not generate a unique referral code after 10 attempts")


async def apply_referral_code(supabase: Client, code: str, referred_user_id: str) -> dict[str, Any]:
    """Link `referred_user_id` to the referrer owning `code`, then complete
    the referral immediately (see module docstring). Idempotent: a user who
    already has a referrals row (referred before, by anyone) gets that
    existing row back rather than erroring — repeat calls from a retried
    frontend request must not raise.
    """

    def _lookup_referrer() -> Optional[str]:
        res = supabase.table("referral_codes").select("user_id").eq("code", code.upper()).execute()
        return res.data[0]["user_id"] if res.data else None

    referrer_user_id = await asyncio.to_thread(_lookup_referrer)
    if not referrer_user_id:
        return {"status": "invalid_code"}
    if referrer_user_id == referred_user_id:
        return {"status": "self_referral_blocked"}

    def _existing() -> Optional[dict[str, Any]]:
        res = supabase.table("referrals").select("*").eq("referred_user_id", referred_user_id).execute()
        return res.data[0] if res.data else None

    if await asyncio.to_thread(_existing):
        return {"status": "already_referred"}

    now = datetime.now(timezone.utc).isoformat()

    def _insert() -> bool:
        try:
            supabase.table("referrals").insert({
                "referred_user_id": referred_user_id,
                "referrer_user_id": referrer_user_id,
                "code": code.upper(),
                "status": "pending",
            }).execute()
            return True
        except APIError as exc:
            if exc.code == _POSTGRES_UNIQUE_VIOLATION:
                return False
            raise

    if not await asyncio.to_thread(_insert):
        return {"status": "already_referred"}

    await _complete_referral(supabase, referrer_user_id, referred_user_id)

    def _mark_completed() -> None:
        supabase.table("referrals").update({
            "status": "completed", "completed_at": now,
        }).eq("referred_user_id", referred_user_id).execute()

    await asyncio.to_thread(_mark_completed)
    return {"status": "completed", "referrer_user_id": referrer_user_id}


async def _complete_referral(supabase: Client, referrer_user_id: str, referred_user_id: str) -> None:
    """Grant both sides 1 month Pro free. Keyed by (source='referral',
    source_id=referred_user_id, user_id) via plan_grants' unique
    constraint, so a retry of the whole apply_referral_code call can't
    double-grant even though this runs before the referrals row is marked
    'completed'."""
    for user_id in (referrer_user_id, referred_user_id):
        await grant_temporary_plan(
            supabase,
            user_id=user_id,
            plan_tier=_REFERRAL_REWARD_PLAN,
            duration_days=_REFERRAL_REWARD_DAYS,
            source="referral",
            source_id=referred_user_id,
        )


async def grant_temporary_plan(
    supabase: Client,
    *,
    user_id: str,
    plan_tier: str,
    duration_days: int,
    source: str,
    source_id: Optional[str],
) -> bool:
    """Record + apply a temporary plan grant. Returns False (no-op) if this
    exact (source, source_id, user_id) grant already exists — the unique
    constraint on plan_grants makes this idempotent under retry, matching
    the claim-first pattern used elsewhere for money-adjacent mutations."""

    def _current_plan() -> str:
        try:
            res = supabase.auth.admin.get_user_by_id(user_id)
            app_metadata = getattr(res.user, "app_metadata", None) or {}
            return app_metadata.get("plan", "free")
        except Exception as exc:
            log.warning("plan_grant_lookup_failed", user_id=user_id, error=str(exc))
            return "free"

    previous_plan = await asyncio.to_thread(_current_plan)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()

    def _insert() -> bool:
        try:
            supabase.table("plan_grants").insert({
                "user_id": user_id,
                "plan_tier": plan_tier,
                "previous_plan": previous_plan,
                "source": source,
                "source_id": source_id,
                "expires_at": expires_at,
            }).execute()
            return True
        except APIError as exc:
            if exc.code == _POSTGRES_UNIQUE_VIOLATION:
                return False
            raise

    if not await asyncio.to_thread(_insert):
        log.info("plan_grant_already_exists", user_id=user_id, source=source, source_id=source_id)
        return False

    # Only actually upgrade the JWT claim if this grant is a real step up —
    # a "pro" grant must never downgrade a user who is already "business".
    from middleware.plan_gate import _PLAN_RANK

    if _PLAN_RANK.get(plan_tier, 0) > _PLAN_RANK.get(previous_plan, 0):
        await set_plan(supabase, user_id, plan_tier)

    log.info("plan_granted", user_id=user_id, plan_tier=plan_tier, source=source, expires_at=expires_at)
    return True


async def get_active_plan_grant(supabase: Client, user_id: str) -> Optional[dict[str, Any]]:
    """The user's current non-expired, non-reverted grant, if any — read by
    GET /api/v1/billing/plan-status. Lazy reversion happens there, not
    here (see migration 034's design note)."""

    def _fetch() -> Optional[dict[str, Any]]:
        res = (
            supabase.table("plan_grants")
            .select("*")
            .eq("user_id", user_id)
            .is_("reverted_at", "null")
            .order("expires_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    return await asyncio.to_thread(_fetch)


async def revert_expired_plan_grant(supabase: Client, grant: dict[str, Any]) -> None:
    """Called once GET /api/v1/billing/plan-status finds `grant` has
    expired: restore the pre-grant plan and mark the grant reverted so it's
    never picked up as "active" again."""

    def _revert() -> None:
        supabase.auth.admin.update_user_by_id(
            grant["user_id"], {"app_metadata": {"plan": grant["previous_plan"]}}
        )
        supabase.table("plan_grants").update({
            "reverted_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", grant["id"]).execute()

    await asyncio.to_thread(_revert)


async def get_referral_summary(supabase: Client, user_id: str) -> dict[str, Any]:
    code = await get_or_create_referral_code(supabase, user_id)

    def _count() -> int:
        res = (
            supabase.table("referrals")
            .select("referred_user_id", count="exact")
            .eq("referrer_user_id", user_id)
            .eq("status", "completed")
            .execute()
        )
        return res.count or 0

    completed = await asyncio.to_thread(_count)
    return {"code": code, "completed_referrals": completed}
