"""Redeem-code fulfillment: a code grants either a credit top-up or a
temporary plan trial. Admin-seeded (manually inserted via SQL, no admin UI
in this pass — see migration 034's header comment).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from postgrest.exceptions import APIError
from supabase import Client

from services.billing import add_credits
from services.referral import grant_temporary_plan

log = structlog.get_logger(__name__)

_POSTGRES_UNIQUE_VIOLATION = "23505"


async def redeem_code(supabase: Client, code: str, user_id: str) -> dict[str, Any]:
    def _lookup() -> Optional[dict[str, Any]]:
        res = supabase.table("redeem_codes").select("*").eq("code", code.upper()).execute()
        return res.data[0] if res.data else None

    row = await asyncio.to_thread(_lookup)
    if not row or not row.get("active"):
        return {"status": "invalid_code"}

    expires_at = row.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now(timezone.utc):
        return {"status": "expired"}

    max_uses = row.get("max_uses")
    if max_uses is not None and row.get("uses_count", 0) >= max_uses:
        return {"status": "exhausted"}

    # Claim-first: insert into the (redeem_code_id, user_id) unique
    # constraint before granting anything, same pattern as
    # services/billing.py's mark_event_processed (Trap #8) — a concurrent
    # double-submit of the same code by the same user can redeem at most
    # once, and this check happens before any credit/plan mutation, not
    # after (no check-then-grant-then-mark race window).
    def _claim() -> bool:
        try:
            supabase.table("redeem_code_redemptions").insert({
                "redeem_code_id": row["id"], "user_id": user_id,
            }).execute()
            return True
        except APIError as exc:
            if exc.code == _POSTGRES_UNIQUE_VIOLATION:
                return False
            raise

    if not await asyncio.to_thread(_claim):
        return {"status": "already_redeemed"}

    try:
        if row["kind"] == "credits":
            await add_credits(supabase, user_id, row["credits_amount"])
            result = {"status": "credits_granted", "credits_amount": row["credits_amount"]}
        else:
            await grant_temporary_plan(
                supabase,
                user_id=user_id,
                plan_tier=row["plan_tier"],
                duration_days=row["plan_duration_days"],
                source="redeem_code",
                source_id=row["id"],
            )
            result = {"status": "plan_granted", "plan_tier": row["plan_tier"], "duration_days": row["plan_duration_days"]}
    except Exception:
        # Fulfillment failed after the claim was already recorded — release
        # the claim so the same code isn't permanently unredeemable for
        # this user (mirrors unmark_event_processed's retry-on-failure
        # rationale in services/billing.py).
        def _release() -> None:
            supabase.table("redeem_code_redemptions").delete().eq(
                "redeem_code_id", row["id"]
            ).eq("user_id", user_id).execute()

        await asyncio.to_thread(_release)
        raise

    def _increment() -> None:
        supabase.table("redeem_codes").update({"uses_count": row.get("uses_count", 0) + 1}).eq("id", row["id"]).execute()

    await asyncio.to_thread(_increment)
    log.info("redeem_code_fulfilled", code=code.upper(), user_id=user_id, kind=row["kind"])
    return result
