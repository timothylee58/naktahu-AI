from typing import Annotated, Literal

import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.config import settings
from services.auth import UserContext, get_current_user
from services.billing import (
    HITPAY_VALID_ITEMS,
    VALID_CHECKOUT_ITEMS,
    create_checkout_session,
    create_hitpay_payment_request,
    get_credits_remaining,
    mark_event_processed,
    mark_hitpay_event_processed,
    process_checkout_completed,
    process_hitpay_webhook,
    unmark_event_processed,
    unmark_hitpay_event_processed,
    verify_hitpay_webhook_signature,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    item: str
    provider: Literal["stripe", "hitpay"] = "stripe"


@router.post("/checkout")
async def post_checkout(
    body: CheckoutRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if body.item not in VALID_CHECKOUT_ITEMS:
        raise HTTPException(status_code=422, detail=f"Unknown checkout item: {body.item}")

    if body.provider == "hitpay":
        if body.item not in HITPAY_VALID_ITEMS:
            raise HTTPException(
                status_code=422,
                detail="HitPay checkout is available for agent credit packs only",
            )
        try:
            url = await create_hitpay_payment_request(
                item=body.item, user_id=user.user_id, user_email=user.email
            )
        except RuntimeError as exc:
            logger.error("hitpay_checkout_session_failed", item=body.item, error=str(exc))
            raise HTTPException(status_code=503, detail="Checkout is temporarily unavailable") from exc
        return {"url": url}

    try:
        url = create_checkout_session(item=body.item, user_id=user.user_id, user_email=user.email)
    except RuntimeError as exc:
        logger.error("checkout_session_failed", item=body.item, error=str(exc))
        raise HTTPException(status_code=503, detail="Checkout is temporarily unavailable") from exc
    return {"url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")

    if not settings.stripe_webhook_secret:
        logger.error("stripe_webhook_secret_not_configured")
        raise HTTPException(status_code=500, detail="Webhook verification is not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        logger.warning("stripe_webhook_invalid_signature", error=str(exc))
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    sb = request.app.state.supabase

    # Claim the event id atomically first (via the stripe_events unique
    # constraint) so two concurrent deliveries of the same event can't both
    # process it. If processing then fails, release the claim so Stripe's
    # automatic retry can reprocess rather than being rejected as a
    # duplicate of a purchase that never actually completed.
    is_new = await mark_event_processed(sb, event["id"])
    if not is_new:
        return {"status": "duplicate"}

    try:
        if event["type"] == "checkout.session.completed":
            await process_checkout_completed(sb, event["data"]["object"])
    except Exception:
        await unmark_event_processed(sb, event["id"])
        raise

    return {"status": "ok"}


@router.post("/webhook/hitpay")
async def hitpay_webhook(request: Request):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")

    if not settings.hitpay_salt:
        logger.error("hitpay_webhook_salt_not_configured")
        raise HTTPException(status_code=500, detail="Webhook verification is not configured")

    form = dict((await request.form()))
    if not verify_hitpay_webhook_signature(form):
        logger.warning("hitpay_webhook_invalid_signature")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payment_id = form.get("payment_id", "")
    if not payment_id:
        raise HTTPException(status_code=400, detail="Missing payment_id")

    sb = request.app.state.supabase

    # Same claim-first, rollback-on-failure pattern as the Stripe webhook —
    # see mark_event_processed's docstring for why the ordering matters.
    is_new = await mark_hitpay_event_processed(sb, payment_id)
    if not is_new:
        return {"status": "duplicate"}

    try:
        await process_hitpay_webhook(sb, form)
    except Exception:
        await unmark_hitpay_event_processed(sb, payment_id)
        raise

    return {"status": "ok"}


@router.get("/credits")
async def get_credits(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")
    remaining = await get_credits_remaining(request.app.state.supabase, user.user_id)
    return {"credits_remaining": remaining}
