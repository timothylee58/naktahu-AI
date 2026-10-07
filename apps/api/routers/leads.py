"""Managed-leads capture — backs the /perniagaan-terurus landing page's
"Book a call" form. Public, no auth (a prospective managed-service client
has no NakTahu account yet, matching the anonymous-friendly precedent in
routers/parliament.py), rate-limited per-IP against spam since this is an
unauthenticated write endpoint with no other quota gating it.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import anonymous_limiter
from services.leads import create_lead

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Loose Malaysian-phone-shaped check (digits, spaces, +, - only) — this is
# spam-friction, not a strict validator; a human reviews every lead anyway.
_PHONE_RE = re.compile(r"^[\d +\-()]{6,20}$")


class LeadRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    company: Optional[str] = Field(None, max_length=200)
    contact_email: Optional[str] = Field(None, max_length=320)
    contact_phone: Optional[str] = Field(None, max_length=32)
    message: Optional[str] = Field(None, max_length=2000)
    # Captured invisibly from ?ref= on the landing page — a free-text
    # partner tag (company-secretary/accountant name), not a code that
    # unlocks anything, so no lookup against any table is needed here.
    referral_source: Optional[str] = Field(None, max_length=100)


@router.post("", status_code=201)
@anonymous_limiter.limit("5/minute")
async def post_lead(request: Request, response: Response, body: LeadRequest):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Lead submission is temporarily unavailable")

    contact_email = body.contact_email.strip() if body.contact_email else None
    contact_phone = body.contact_phone.strip() if body.contact_phone else None
    if not contact_email and not contact_phone:
        raise HTTPException(status_code=422, detail="Provide at least one of contact_email or contact_phone")
    if contact_email and not _EMAIL_RE.match(contact_email):
        raise HTTPException(status_code=422, detail="contact_email is not a valid email address")
    if contact_phone and not _PHONE_RE.match(contact_phone):
        raise HTTPException(status_code=422, detail="contact_phone is not a valid phone number")

    lead = await create_lead(
        request.app.state.supabase,
        name=body.name.strip(),
        company=body.company.strip() if body.company else None,
        contact_email=contact_email,
        contact_phone=contact_phone,
        message=body.message.strip() if body.message else None,
        referral_source=body.referral_source.strip() if body.referral_source else None,
    )
    return {"id": lead.get("id")}
