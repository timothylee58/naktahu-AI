"""GET /api/v1/health — liveness + dependency probe."""
from __future__ import annotations

import os

import structlog
from fastapi import APIRouter

from app.services.cache import ping as redis_ping

log = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


async def _supabase_ping() -> bool:
    try:
        from supabase import acreate_client

        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            return False
        client = await acreate_client(url, key)
        # lightweight probe — list tables (returns empty on restricted key, not an error)
        await client.table("document_chunks").select("id").limit(1).execute()
        return True
    except Exception:
        return False


@router.get("/health")
@router.get("/api/v1/health")
async def health() -> dict:
    redis_ok = await redis_ping()
    supabase_ok = await _supabase_ping()
    log.info("health_check", redis=redis_ok, supabase=supabase_ok)
    return {"status": "ok", "redis": redis_ok, "supabase": supabase_ok}
