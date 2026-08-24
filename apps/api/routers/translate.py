from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from middleware.rate_limit import apply_query_rate_limit
from routers._request_fields import Language, normalise_language
from services.auth import UserContext, get_optional_user
from services.translate import translate_text

router = APIRouter(prefix="/api/v1", tags=["translate"])

# One chat answer's worth of text — generous over the longest realistic
# synthesised answer, well short of letting this become a free-form LLM
# text-processing proxy via an oversized payload.
_MAX_TEXT_CHARS = 8000


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=_MAX_TEXT_CHARS)
    target_language: Language

    @field_validator("target_language")
    @classmethod
    def _normalise_target(cls, v: Language) -> Language:
        return normalise_language(v)


@router.post("/translate")
@apply_query_rate_limit()
async def post_translate(
    request: Request,
    response: Response,
    body: TranslateRequest,
    optional_user: Annotated[Optional[UserContext], Depends(get_optional_user)],
):
    """No Supabase dependency — pure LLM pass-through, nothing is read or
    written to any table, so this keeps working in degraded mode the same
    way the property-listing OCR endpoint does."""
    translated = await translate_text(body.text, body.target_language)
    if not translated:
        raise HTTPException(status_code=502, detail="Translation failed. Please try again.")
    return {"translated_text": translated, "target_language": body.target_language}
