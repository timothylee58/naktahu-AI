"""GET /api/v1/health — liveness + dependency probe."""
from __future__ import annotations

import os

import structlog
from fastapi import APIRouter

from app.agents.checkpointer import get_checkpointer_backend
from app.services.cache import ping as redis_ping
from middleware.rate_limit import get_rate_limit_backend

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
    # "memory" here (when a Postgres checkpointer was actually configured)
    # means every multi-turn agent session gets wiped on the next restart —
    # previously only a single warning log line at boot, easy to miss.
    checkpointer_backend = get_checkpointer_backend()
    rate_limit_backend = get_rate_limit_backend()
    log.info(
        "health_check",
        redis=redis_ok,
        supabase=supabase_ok,
        checkpointer=checkpointer_backend,
        rate_limiter=rate_limit_backend,
    )
    return {
        "status": "ok",
        "redis": redis_ok,
        "supabase": supabase_ok,
        "checkpointer": checkpointer_backend,
        "rate_limiter": rate_limit_backend,
    }
