from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_current_user
from services.property_submissions import (
    MAX_LISTING_IMAGE_B64_CHARS,
    extract_listing_from_image,
    list_my_listings,
    submit_listing,
)

router = APIRouter(prefix="/api/v1/property/listings", tags=["property-listings"])

_PROPERTY_TYPES = {"condo", "apartment", "landed", "other"}
_ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ListingSubmitRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=500)
    title: Optional[str] = Field(None, max_length=200)
    price_myr: Optional[float] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=120)
    property_type: Optional[str] = None
    bedrooms: Optional[int] = Field(None, ge=0, le=50)
    notes: Optional[str] = Field(None, max_length=1000)


@router.post("", status_code=201)
@apply_query_rate_limit()
async def post_listing_submission(
    request: Request,
    response: Response,
    body: ListingSubmitRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Listing submission is temporarily unavailable")
    if body.property_type is not None and body.property_type not in _PROPERTY_TYPES:
        raise HTTPException(status_code=422, detail=f"property_type must be one of {sorted(_PROPERTY_TYPES)}")
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="url must start with http:// or https://")

    return await submit_listing(
        request.app.state.supabase,
        user.user_id,
        url=body.url,
        title=body.title,
        price_myr=body.price_myr,
        location=body.location,
        property_type=body.property_type,
        bedrooms=body.bedrooms,
        notes=body.notes,
    )


class ListingOcrRequest(BaseModel):
    image_base64: str = Field(..., min_length=16, max_length=MAX_LISTING_IMAGE_B64_CHARS)
    mime_type: str = Field("image/jpeg", max_length=20)
    language: str = Field("bm", max_length=2)


@router.post("/ocr")
@apply_query_rate_limit()
async def post_listing_ocr(
    request: Request,
    response: Response,
    body: ListingOcrRequest,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    """Extracts prefill fields from a photographed/screenshotted listing.
    Does not write anything — the caller still POSTs to / to actually
    submit, after reviewing/editing whatever came back here."""
    if body.mime_type not in _ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(status_code=422, detail=f"mime_type must be one of {sorted(_ALLOWED_IMAGE_MIME_TYPES)}")
    if body.language not in {"bm", "en", "zh"}:
        raise HTTPException(status_code=422, detail="language must be one of ['bm', 'en', 'zh']")

    fields = await extract_listing_from_image(
        body.image_base64,
        mime_type=body.mime_type,
        language=body.language,
    )
    return {"fields": fields}


@router.get("/mine")
@apply_query_rate_limit()
async def get_my_listings(
    request: Request,
    response: Response,
    user: Annotated[UserContext, Depends(get_current_user)],
):
    if not request.app.state.supabase:
        raise HTTPException(status_code=503, detail="Listing submission is temporarily unavailable")
    listings = await list_my_listings(request.app.state.supabase, user.user_id)
    return {"listings": listings}
