from datetime import datetime, timezone
from typing import Annotated, Literal

import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core.config import settings
from middleware.rate_limit import apply_query_rate_limit
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
from services.redeem_codes import redeem_code
from services.referral import get_active_plan_grant, revert_expired_plan_grant

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


class RedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=32)


@router.post("/redeem")
@apply_query_rate_limit()
async def post_redeem_code(
    request: Request,
    response: Response,
    body: RedeemCodeRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")
    result = await redeem_code(request.app.state.supabase, body.code, user.user_id)
    if result["status"] == "invalid_code":
        raise HTTPException(status_code=404, detail="Redeem code not found")
    if result["status"] in ("expired", "exhausted", "already_redeemed"):
        raise HTTPException(status_code=409, detail=result["status"].replace("_", " "))
    return result


@router.get("/plan-status")
async def get_plan_status(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    """The caller's active temporary plan grant, if any — surfaced on the
    profile page since a referral/redeem-code grant is not reflected in the
    plan badge until the JWT is next refreshed (see migration 034's design
    note). Also where lazy expiry reversion happens: an expired grant found
    here is reverted immediately, before being reported, so the response
    never claims an already-expired grant is still active."""
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")
    sb = request.app.state.supabase
    grant = await get_active_plan_grant(sb, user.user_id)
    if not grant:
        return {"active_grant": None}

    expires_at = datetime.fromisoformat(grant["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        await revert_expired_plan_grant(sb, grant)
        return {"active_grant": None}

    return {
        "active_grant": {
            "plan_tier": grant["plan_tier"],
            "source": grant["source"],
            "expires_at": grant["expires_at"],
        }
    }
