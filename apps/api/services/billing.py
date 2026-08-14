"""Stripe + HitPay checkout, webhook processing, and agent credit ledger.

Two kinds of purchase:
- Plan items (subscription mode, Stripe only) — on completion, sets the
  Supabase user's app_metadata.plan via the admin API. Takes effect on the
  user's next JWT refresh (the frontend forces one on the checkout success
  redirect).
- Credit items (one-time payment) — on completion, tops up agent_credits.
  Available via either Stripe (card) or HitPay (FPX/DuitNow QR) — HitPay is
  scoped to credit packs only for now; its recurring-billing surface hasn't
  been evaluated, so plan subscriptions stay Stripe-only.

Webhook delivery is at-least-once, not exactly-once for both providers —
stripe_events / hitpay_events dedupe by the provider's event/payment id
before either path runs.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as hmac_lib
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
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
    # Annual variants — same resulting plan claim as monthly, different
    # Stripe Price (see core/config.py for the discount rationale).
    "pro_individu_annual": ("stripe_price_pro_individu_annual", "pro"),
    "pro_perniagaan_annual": ("stripe_price_pro_perniagaan_annual", "business"),
    "student_annual": ("stripe_price_student_annual", "student"),
}

# item -> (Stripe price env attr, credit count)
_CREDIT_ITEMS: dict[str, tuple[str, int]] = {
    "credits_5": ("stripe_price_credits_5", 5),
    "credits_20": ("stripe_price_credits_20", 20),
    "credits_50": ("stripe_price_credits_50", 50),
}

VALID_CHECKOUT_ITEMS = set(_PLAN_ITEMS) | set(_CREDIT_ITEMS)

# RM per agent credit (matches the pricing page and CLAUDE.md's "RM 5 per
# credit" — HitPay takes a raw MYR amount rather than a Stripe-style price
# ID, so the amount is derived from the credit count here instead of being
# configured per item).
CREDIT_PRICE_MYR = 5
HITPAY_VALID_ITEMS = set(_CREDIT_ITEMS)


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


async def create_hitpay_payment_request(
    *, item: str, user_id: str, user_email: Optional[str]
) -> str:
    """Create a HitPay payment request (FPX/DuitNow QR) for a credit pack
    and return its checkout URL. Credit packs only — see module docstring.

    HitPay has no arbitrary metadata field like Stripe's Checkout Session,
    so the (item, user_id) pair needed to credit the right account on
    webhook delivery is encoded into reference_number and parsed back out
    in process_hitpay_webhook.
    """
    if item not in HITPAY_VALID_ITEMS:
        raise ValueError(f"HitPay checkout is credit-packs only, got: {item}")
    if not settings.hitpay_api_key:
        raise RuntimeError("HitPay API key not configured")

    _price_attr, credits = _CREDIT_ITEMS[item]
    amount = credits * CREDIT_PRICE_MYR
    reference_number = f"{item}:{user_id}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.hitpay_base_url}/payment-requests",
                headers={"X-BUSINESS-API-KEY": settings.hitpay_api_key},
                data={
                    "amount": str(amount),
                    "currency": "MYR",
                    "email": user_email or "",
                    "reference_number": reference_number,
                    "redirect_url": f"{settings.frontend_url}/pricing?checkout=success",
                    "webhook": f"{settings.public_api_url}/api/v1/billing/webhook/hitpay",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("hitpay_checkout_failed", item=item, error=str(exc))
            raise RuntimeError("HitPay did not return a checkout URL") from exc

    data = resp.json()
    url = data.get("url")
    if not url:
        raise RuntimeError("HitPay did not return a checkout URL")
    return url


def verify_hitpay_webhook_signature(form: dict[str, str]) -> bool:
    """HMAC-SHA256 over the sorted, concatenated key+value pairs of every
    field except `hmac`, keyed by the HitPay salt (a separate secret from
    the API key — Settings > Payment Gateway > Webhook in the dashboard).
    This is HitPay's documented scheme, distinct from Stripe's
    timestamp-based Hitpay-Signature-style header verification.
    """
    received = form.get("hmac", "")
    if not received or not settings.hitpay_salt:
        return False

    fields = {k: v for k, v in form.items() if k != "hmac"}
    concatenated = "".join(f"{k}{fields[k]}" for k in sorted(fields))
    expected = hmac_lib.new(
        settings.hitpay_salt.encode(), concatenated.encode(), hashlib.sha256
    ).hexdigest()
    return hmac_lib.compare_digest(expected, received)


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


async def mark_hitpay_event_processed(supabase_client: Client, payment_id: str) -> bool:
    """Same atomic-claim pattern as mark_event_processed, against the
    separate hitpay_events table (HitPay's payment_id is not comparable to
    a Stripe event id, so it gets its own idempotency ledger rather than
    sharing stripe_events)."""

    def _insert() -> bool:
        try:
            supabase_client.table("hitpay_events").insert({"hitpay_payment_id": payment_id}).execute()
            return True
        except APIError as exc:
            if exc.code == _POSTGRES_UNIQUE_VIOLATION:
                return False
            raise

    return await asyncio.to_thread(_insert)


async def unmark_hitpay_event_processed(supabase_client: Client, payment_id: str) -> None:
    def _delete() -> None:
        supabase_client.table("hitpay_events").delete().eq("hitpay_payment_id", payment_id).execute()

    await asyncio.to_thread(_delete)


async def process_hitpay_webhook(supabase_client: Client, form: dict[str, str]) -> None:
    reference_number = form.get("reference_number", "")
    status = form.get("status", "")

    item, _sep, user_id = reference_number.partition(":")
    if not item or not user_id or item not in HITPAY_VALID_ITEMS:
        logger.warning("hitpay_webhook_unrecognised_reference", reference_number=reference_number)
        return

    if status != "completed":
        logger.info("hitpay_webhook_ignored_status", status=status, reference_number=reference_number)
        return

    _price_attr, credits = _CREDIT_ITEMS[item]
    await add_credits(supabase_client, user_id, credits)
    logger.info("hitpay_credits_added", user_id=user_id, credits=credits, item=item)


async def process_checkout_completed(supabase_client: Client, session_data: dict[str, Any]) -> None:
    metadata = session_data.get("metadata") or {}
    user_id = metadata.get("user_id")
    item = metadata.get("item")

    if not user_id or not item:
        logger.warning("stripe_webhook_missing_metadata", session_id=session_data.get("id"))
        return

    if item in _PLAN_ITEMS:
        _price_attr, plan = _PLAN_ITEMS[item]
        await set_plan(supabase_client, user_id, plan)
        logger.info("stripe_plan_updated", user_id=user_id, plan=plan, item=item)
    elif item in _CREDIT_ITEMS:
        _price_attr, credits = _CREDIT_ITEMS[item]
        await add_credits(supabase_client, user_id, credits)
        logger.info("stripe_credits_added", user_id=user_id, credits=credits, item=item)
    else:
        logger.warning("stripe_webhook_unknown_item", item=item, user_id=user_id)


async def set_plan(supabase_client: Client, user_id: str, plan: str) -> None:
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


async def deduct_credits(supabase_client: Optional[Client], user_id: str, n: int) -> int:
    """Atomically deduct credits via deduct_agent_credits RPC.

    Returns remaining balance, or -1 if insufficient credits or no client.
    """
    if not supabase_client or n <= 0:
        return -1

    def _rpc() -> int:
        res = supabase_client.rpc(
            "deduct_agent_credits", {"p_user_id": user_id, "p_amount": n}
        ).execute()
        if res.data is None:
            return -1
        return int(res.data)

    return await asyncio.to_thread(_rpc)
