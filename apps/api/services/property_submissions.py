"""User-submitted property listings — the legitimate alternative to
property_concierge sourcing live listings itself (see that agent's module
docstring for why it doesn't scrape PropertyGuru/iProperty/Mudah or bypass
NAPIC's licensed-valuer gate). The user pastes a listing URL + details they
found themselves; nothing here is fetched or verified server-side.

Credit reward is disclosed on the submission form itself (not concealed)
and is idempotent per (user_id, url) via the table's UNIQUE constraint —
resubmitting the same URL is a silent no-op, so it can't be farmed.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import HTTPException
from supabase import Client

from app.agents.tools import ocr_extract_listing_fields
from app.middleware.sanitise import INJECTION_PATTERNS, _fold_confusables
from services.billing import add_credits

SUBMISSION_CREDIT_REWARD = 1

# Base64 image size guard — mirrors app/routers/transcribe.py's
# _MAX_AUDIO_B64_CHARS reasoning: ~9M base64 chars ≈ ~6.7MB decoded, a
# generous ceiling for a phone photo/screenshot without letting an
# oversized payload through to the vision call.
MAX_LISTING_IMAGE_B64_CHARS = 9_000_000


def _check_injection(text: Optional[str]) -> None:
    """Same scan ingest_feed.py runs before anything reaches document_chunks
    (Trap: 'no ingestion path is exempt') — applied here too because a
    submission's title/notes could later be read back into an LLM prompt
    (e.g. if property_concierge's synthesis surfaces user submissions),
    same prompt-injection exposure as any other user-authored text an
    agent might read."""
    if not text:
        return
    folded = _fold_confusables(text)
    for pattern in INJECTION_PATTERNS:
        if pattern.search(folded):
            raise HTTPException(status_code=422, detail="Submission contains disallowed content.")


async def submit_listing(
    supabase_client: Client,
    user_id: str,
    *,
    url: str,
    title: Optional[str] = None,
    price_myr: Optional[float] = None,
    location: Optional[str] = None,
    property_type: Optional[str] = None,
    bedrooms: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    _check_injection(title)
    _check_injection(location)
    _check_injection(notes)

    row = {
        "user_id": user_id,
        "url": url,
        "title": title,
        "price_myr": price_myr,
        "location": location,
        "property_type": property_type,
        "bedrooms": bedrooms,
        "notes": notes,
    }

    def _insert():
        # ON CONFLICT DO NOTHING on the (user_id, url) UNIQUE constraint —
        # resubmitting a URL this user already submitted is a no-op, not
        # an error, and (critically) awards no second credit.
        return (
            supabase_client.table("property_listing_submissions")
            .upsert(row, on_conflict="user_id,url", ignore_duplicates=True)
            .execute()
        )

    result = await asyncio.to_thread(_insert)
    inserted = bool(result.data)

    credits_awarded = 0
    if inserted:
        await add_credits(supabase_client, user_id, SUBMISSION_CREDIT_REWARD)
        credits_awarded = SUBMISSION_CREDIT_REWARD

        def _mark_awarded():
            supabase_client.table("property_listing_submissions").update(
                {"credit_awarded": True}
            ).eq("user_id", user_id).eq("url", url).execute()

        await asyncio.to_thread(_mark_awarded)

    return {"submitted": inserted, "credits_awarded": credits_awarded}


async def extract_listing_from_image(
    image_base64: str,
    *,
    mime_type: str = "image/jpeg",
    language: str = "bm",
) -> dict[str, Any]:
    """OCR a photo/screenshot of a listing into prefill fields for the
    submission form. Nothing is stored or submitted here — the image is
    never persisted (not uploaded to Supabase Storage, not written to any
    table); it only ever reaches the vision model as a one-shot base64
    payload. The extracted fields still pass through the same
    injection-scan/submit_listing path as manually-typed fields once the
    user reviews and confirms them via POST /api/v1/property/listings, so
    this function never bypasses the "unverified, user-confirmed" model."""
    fields = await ocr_extract_listing_fields(image_base64, mime_type=mime_type, language=language)
    _check_injection(fields.get("title"))
    _check_injection(fields.get("location"))
    return fields


async def list_my_listings(supabase_client: Client, user_id: str) -> list[dict[str, Any]]:
    def _fetch():
        return (
            supabase_client.table("property_listing_submissions")
            .select("id,url,title,price_myr,location,property_type,bedrooms,status,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )

    result = await asyncio.to_thread(_fetch)
    return result.data or []
