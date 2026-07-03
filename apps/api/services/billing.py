"""Stripe checkout, webhook processing, and agent credit ledger.

Two kinds of purchase:
- Plan items (subscription mode) — on completion, sets the Supabase user's
  app_metadata.plan via the admin API. Takes effect on the user's next JWT
  refresh (the frontend forces one on the checkout success redirect).
- Credit items (payment mode) — on completion, tops up agent_credits.

Webhook delivery is at-least-once, not exactly-once — stripe_events dedupes
by Stripe's event id before either path runs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import stripe
import structlog
from postgrest.exceptions import APIError
from supabase import Client

from core.config import settings

logger = structlog.get_logger()

stripe.api_key = settings.stripe_secret_key

_POSTGRES_UNIQUE_VIOLATION = "23505"

# item -> (Stripe price env attr, resulting plan claim)
_PLAN_ITEMS: dict[str, tuple[str, str]] = {
    "pro_individu": ("stripe_price_pro_individu", "pro"),
    "pro_perniagaan": ("stripe_price_pro_perniagaan", "business"),
    "student": ("stripe_price_student", "student"),
}

# item -> (Stripe price env attr, credit count)
_CREDIT_ITEMS: dict[str, tuple[str, int]] = {
    "credits_5": ("stripe_price_credits_5", 5),
    "credits_20": ("stripe_price_credits_20", 20),
    "credits_50": ("stripe_price_credits_50", 50),
}

VALID_CHECKOUT_ITEMS = set(_PLAN_ITEMS) | set(_CREDIT_ITEMS)


def create_checkout_session(
    *, item: str, user_id: str, user_email: Optional[str]
) -> str:
    """Create a Stripe Checkout session and return its redirect URL."""
    if item in _PLAN_ITEMS:
        price_attr, _plan = _PLAN_ITEMS[item]
        mode = "subscription"
    elif item in _CREDIT_ITEMS:
        price_attr, _credits = _CREDIT_ITEMS[item]
        mode = "payment"
    else:
        raise ValueError(f"Unknown checkout item: {item}")

    price_id = getattr(settings, price_attr)
    if not price_id:
        raise RuntimeError(f"Stripe price not configured for item '{item}' ({price_attr})")

    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.frontend_url}/pricing?checkout=success",
        cancel_url=f"{settings.frontend_url}/pricing?checkout=canceled",
        client_reference_id=user_id,
        customer_email=user_email,
        metadata={"user_id": user_id, "item": item},
    )
    if not session.url:
        raise RuntimeError("Stripe did not return a checkout URL")
    return session.url


async def mark_event_processed(supabase_client: Client, event_id: str) -> bool:
    """Atomically claim the Stripe event id via the unique constraint.

    Returns False if already claimed (duplicate delivery — including a
    concurrent delivery of the same event, which Stripe does send). Must be
    paired with unmark_event_processed() on processing failure so a
    transient error doesn't permanently blacklist a retryable event.
    """

    def _insert() -> bool:
        try:
            supabase_client.table("stripe_events").insert({"stripe_event_id": event_id}).execute()
            return True
        except APIError as exc:
            if exc.code == _POSTGRES_UNIQUE_VIOLATION:
                return False
            raise

    return await asyncio.to_thread(_insert)


async def unmark_event_processed(supabase_client: Client, event_id: str) -> None:
    """Release a claimed event id after processing fails, so Stripe's
    automatic retry can reprocess it instead of being rejected as a
    duplicate of a purchase that never actually completed."""

    def _delete() -> None:
        supabase_client.table("stripe_events").delete().eq("stripe_event_id", event_id).execute()

    await asyncio.to_thread(_delete)


async def process_checkout_completed(supabase_client: Client, session_data: dict[str, Any]) -> None:
    metadata = session_data.get("metadata") or {}
    user_id = metadata.get("user_id")
    item = metadata.get("item")

    if not user_id or not item:
        logger.warning("stripe_webhook_missing_metadata", session_id=session_data.get("id"))
        return

    if item in _PLAN_ITEMS:
        _price_attr, plan = _PLAN_ITEMS[item]
        await _set_plan(supabase_client, user_id, plan)
        logger.info("stripe_plan_updated", user_id=user_id, plan=plan, item=item)
    elif item in _CREDIT_ITEMS:
        _price_attr, credits = _CREDIT_ITEMS[item]
        await add_credits(supabase_client, user_id, credits)
        logger.info("stripe_credits_added", user_id=user_id, credits=credits, item=item)
    else:
        logger.warning("stripe_webhook_unknown_item", item=item, user_id=user_id)


async def _set_plan(supabase_client: Client, user_id: str, plan: str) -> None:
    def _update() -> None:
        supabase_client.auth.admin.update_user_by_id(user_id, {"app_metadata": {"plan": plan}})

    await asyncio.to_thread(_update)


async def add_credits(supabase_client: Client, user_id: str, n: int) -> None:
    """Atomic top-up via the add_agent_credits RPC (infra/supabase/migrations/007_billing.sql).

    A select-then-update/insert from here would race under concurrent
    webhook deliveries — two calls could both read the same starting
    balance and each write current+n, silently losing one top-up. The RPC
    does the read-modify-write inside a single statement under Postgres's
    row lock, so concurrent calls always sum correctly.
    """

    def _rpc() -> None:
        now = datetime.now(timezone.utc).isoformat()
        supabase_client.rpc(
            "add_agent_credits", {"p_user_id": user_id, "p_amount": n, "p_now": now}
        ).execute()

    await asyncio.to_thread(_rpc)


async def get_credits_remaining(supabase_client: Optional[Client], user_id: str) -> int:
    if not supabase_client:
        return 0

    def _fetch() -> int:
        res = (
            supabase_client.table("agent_credits")
            .select("credits_remaining")
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0]["credits_remaining"] if res.data else 0

    return await asyncio.to_thread(_fetch)
