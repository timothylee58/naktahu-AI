"""POST /api/v1/session/migrate — migrate anonymous history to authenticated account."""
from __future__ import annotations

import re
from typing import Optional

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.routers.query import _extract_user_id
from app.services.cache import _get_client

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["session"])

_ANON_ID_RE = re.compile(r"^[0-9a-f\-]{36}$")  # UUID v4 format


class MigrateRequest(BaseModel):
    anonymous_id: str = Field(..., min_length=36, max_length=36)


class MigrateResponse(BaseModel):
    migrated: bool
    entries_moved: int


@router.post("/session/migrate", response_model=MigrateResponse)
async def migrate_session(
    body: MigrateRequest,
    authorization: Optional[str] = Header(default=None),
) -> MigrateResponse:
    user_id = _extract_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    if not _ANON_ID_RE.match(body.anonymous_id):
        raise HTTPException(status_code=422, detail="Invalid anonymous_id format.")

    anon_key = f"session:{body.anonymous_id}:history"
    user_key = f"session:{user_id}:history"

    try:
        client = _get_client()
        entries = await client.lrange(anon_key, 0, -1)
        if not entries:
            return MigrateResponse(migrated=False, entries_moved=0)

        pipe = client.pipeline()
        # Prepend anon history to authenticated history (oldest first to preserve order)
        for entry in reversed(entries):
            pipe.lpush(user_key, entry)
        pipe.ltrim(user_key, 0, 49)  # cap at 50
        pipe.expire(user_key, 2592000)  # 30 days
        pipe.delete(anon_key)
        await pipe.execute()

        log.info("session_migrated", user_id=user_id, entries=len(entries))
        return MigrateResponse(migrated=True, entries_moved=len(entries))

    except Exception as exc:
        log.error("session_migrate_error", error=str(exc), user_id=user_id)
        raise HTTPException(status_code=500, detail="Migration failed.") from exc
