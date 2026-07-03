from typing import Annotated

import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.config import settings
from services.auth import UserContext, get_current_user
from services.billing import (
    VALID_CHECKOUT_ITEMS,
    create_checkout_session,
    get_credits_remaining,
    mark_event_processed,
    process_checkout_completed,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    item: str


@router.post("/checkout")
async def post_checkout(
    body: CheckoutRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if body.item not in VALID_CHECKOUT_ITEMS:
        raise HTTPException(status_code=422, detail=f"Unknown checkout item: {body.item}")
    try:
        url = create_checkout_session(item=body.item, user_id=user.user_id, user_email=None)
    except RuntimeError as exc:
        logger.error("checkout_session_failed", item=body.item, error=str(exc))
        raise HTTPException(status_code=503, detail="Checkout is temporarily unavailable") from exc
    return {"url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Billing service temporarily unavailable")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        logger.warning("stripe_webhook_invalid_signature", error=str(exc))
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    sb = request.app.state.supabase
    is_new = await mark_event_processed(sb, event["id"])
    if not is_new:
        return {"status": "duplicate"}

    if event["type"] == "checkout.session.completed":
        await process_checkout_completed(sb, event["data"]["object"])

    return {"status": "ok"}


@router.get("/credits")
async def get_credits(
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    remaining = await get_credits_remaining(request.app.state.supabase, user.user_id)
    return {"credits_remaining": remaining}
