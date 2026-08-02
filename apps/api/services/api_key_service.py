"""API key generation, validation, and usage metering."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from redis.asyncio import Redis
from supabase import Client

logger = structlog.get_logger()

API_KEY_RAW_PREFIX = "nkt_live_"

API_PLAN_DEFAULTS: dict[str, dict[str, Any]] = {
    "free": {
        "calls_limit": 500,
        "rate_limit_per_min": 5,
        "sse": False,
        "multi": False,
        "widget": False,
        "white_label": False,
    },
    "starter": {
        "calls_limit": 5500,
        "rate_limit_per_min": 10,
        "sse": False,
        "multi": False,
        "widget": False,
        "white_label": False,
    },
    "growth": {
        "calls_limit": 50000,
        "rate_limit_per_min": 60,
        "sse": True,
        "multi": True,
        "widget": False,
        "white_label": False,
    },
    "enterprise": {
        "calls_limit": 9_999_999,
        "rate_limit_per_min": 1000,
        "sse": True,
        "multi": True,
        "widget": True,
        "white_label": True,
    },
    "widget": {
        "calls_limit": 5500,
        "rate_limit_per_min": 10,
        "sse": False,
        "multi": False,
        "widget": True,
        "white_label": False,
    },
    "white_label": {
        "calls_limit": 50000,
        "rate_limit_per_min": 30,
        "sse": False,
        "multi": False,
        "widget": True,
        "white_label": True,
    },
}

VALID_API_PLANS = frozenset(API_PLAN_DEFAULTS.keys())
MAX_KEYS_PER_USER = 3


@dataclass(frozen=True)
class ApiKeyContext:
    key_id: str
    user_id: str
    plan: str
    calls_used: int
    calls_limit: int
    rate_limit_per_min: int
    domain_whitelist: list[str]
    white_label: bool
    widget: bool
    sse: bool
    multi: bool


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return (raw_key, key_hash, key_prefix). Raw key shown once only."""
    raw_key = f"{API_KEY_RAW_PREFIX}{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:16]
    return raw_key, key_hash, key_prefix


def plan_features(plan: str) -> dict[str, Any]:
    return API_PLAN_DEFAULTS.get(plan, API_PLAN_DEFAULTS["starter"])


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _usage_redis_key(key_id: str) -> str:
    return f"api_key:usage:{key_id}:{_month_key()}"


def _row_to_context(row: dict[str, Any]) -> ApiKeyContext:
    plan = str(row.get("plan") or "starter")
    features = plan_features(plan)
    whitelist = row.get("domain_whitelist") or []
    if not isinstance(whitelist, list):
        whitelist = []
    return ApiKeyContext(
        key_id=str(row["id"]),
        user_id=str(row["user_id"]),
        plan=plan,
        calls_used=int(row.get("calls_used") or 0),
        calls_limit=int(row.get("calls_limit") or features["calls_limit"]),
        rate_limit_per_min=int(row.get("rate_limit_per_min") or features["rate_limit_per_min"]),
        domain_whitelist=[str(d) for d in whitelist],
        white_label=bool(features["white_label"]),
        widget=bool(features["widget"]),
        sse=bool(features["sse"]),
        multi=bool(features["multi"]),
    )


async def validate_api_key(
    supabase: Optional[Client],
    redis_client: Optional[Redis],
    raw_key: str,
) -> Optional[ApiKeyContext]:
    """Validate raw API key: hash lookup, active flag, monthly quota."""
    if not raw_key or not raw_key.startswith(API_KEY_RAW_PREFIX):
        return None
    if supabase is None:
        return None

    key_hash = hash_api_key(raw_key)

    def _fetch() -> Optional[dict[str, Any]]:
        res = (
            supabase.table("api_keys")
            .select("*")
            .eq("key_hash", key_hash)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None

    row = await asyncio.to_thread(_fetch)
    if not row:
        return None

    ctx = _row_to_context(row)

    if redis_client is not None:
        redis_used = await redis_client.get(_usage_redis_key(ctx.key_id))
        if redis_used is not None:
            try:
                ctx = ApiKeyContext(
                    **{**ctx.__dict__, "calls_used": max(ctx.calls_used, int(redis_used))}
                )
            except (TypeError, ValueError):
                pass

    if ctx.calls_used >= ctx.calls_limit:
        return None

    return ctx


def origin_allowed(ctx: ApiKeyContext, origin: Optional[str]) -> bool:
    """Widget keys require Origin to match domain_whitelist when set."""
    if not ctx.domain_whitelist:
        return True
    if not origin:
        return False
    origin_host = origin.lower().rstrip("/")
    for allowed in ctx.domain_whitelist:
        norm = allowed.lower().rstrip("/")
        if origin_host == norm or origin_host.endswith(f".{norm.lstrip('*.')}"):
            return True
        if norm.startswith("*.") and origin_host.endswith(norm[1:]):
            return True
    return False


async def increment_usage(
    redis_client: Optional[Redis],
    supabase: Optional[Client],
    key_id: str,
) -> int:
    """Atomic Redis INCR for monthly usage + async Supabase sync. Returns new count."""
    count = 1
    if redis_client is not None:
        redis_key = _usage_redis_key(key_id)
        count = int(await redis_client.incr(redis_key))
        if count == 1:
            await redis_client.expire(redis_key, 60 * 60 * 24 * 35)

    if supabase is not None:

        def _update() -> None:
            supabase.table("api_keys").update(
                {
                    "calls_used": count,
                    "last_used_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", key_id).execute()

        await asyncio.to_thread(_update)

    return count


async def log_api_key_event(
    supabase: Optional[Client],
    *,
    key_id: str,
    endpoint: str,
    domain: Optional[str],
    response_ms: int,
    cache_hit: bool = False,
) -> None:
    if supabase is None:
        return

    row = {
        "key_id": key_id,
        "endpoint": endpoint,
        "domain": domain,
        "response_ms": response_ms,
        "cache_hit": cache_hit,
    }

    def _insert() -> None:
        supabase.table("api_key_events").insert(row).execute()

    try:
        await asyncio.to_thread(_insert)
    except Exception as exc:
        logger.warning("api_key_event_log_failed", key_id=key_id, error=str(exc))


async def create_api_key_record(
    supabase: Client,
    *,
    user_id: str,
    plan: str,
    domain_whitelist: Optional[list[str]] = None,
) -> tuple[str, dict[str, Any]]:
    """Insert key row; return (raw_key, public_row without hash)."""
    if plan not in VALID_API_PLANS:
        raise ValueError(f"Invalid API plan: {plan}")

    def _count() -> int:
        res = (
            supabase.table("api_keys")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        return int(res.count or 0)

    active_count = await asyncio.to_thread(_count)
    if active_count >= MAX_KEYS_PER_USER:
        raise ValueError("max_keys_reached")

    raw_key, key_hash, key_prefix = generate_api_key()
    features = plan_features(plan)
    row = {
        "user_id": user_id,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "plan": plan,
        "calls_limit": features["calls_limit"],
        "rate_limit_per_min": features["rate_limit_per_min"],
        "domain_whitelist": domain_whitelist or [],
        "active": True,
    }

    def _insert() -> dict[str, Any]:
        res = supabase.table("api_keys").insert(row).select("*").execute()
        return (res.data or [{}])[0]

    inserted = await asyncio.to_thread(_insert)
    public = {k: v for k, v in inserted.items() if k != "key_hash"}
    return raw_key, public


async def list_api_keys(supabase: Client, user_id: str) -> list[dict[str, Any]]:
    def _fetch() -> list[dict[str, Any]]:
        res = (
            supabase.table("api_keys")
            .select(
                "id, key_prefix, plan, calls_used, calls_limit, rate_limit_per_min, "
                "domain_whitelist, active, last_used_at, created_at"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(res.data or [])

    return await asyncio.to_thread(_fetch)


async def revoke_api_key(supabase: Client, user_id: str, key_id: str) -> bool:
    def _revoke() -> bool:
        res = (
            supabase.table("api_keys")
            .update({"active": False})
            .eq("id", key_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(res.data)

    return await asyncio.to_thread(_revoke)


async def fetch_usage_stats(
    supabase: Client,
    user_id: str,
    *,
    days: int = 30,
) -> dict[str, Any]:
    """Aggregate usage by domain and endpoint for the user's keys."""

    def _fetch() -> list[dict[str, Any]]:
        keys_res = (
            supabase.table("api_keys")
            .select("id, key_prefix, plan, calls_used, calls_limit")
            .eq("user_id", user_id)
            .execute()
        )
        key_ids = [k["id"] for k in (keys_res.data or [])]
        if not key_ids:
            return []

        events_res = (
            supabase.table("api_key_events")
            .select("endpoint, domain, created_at")
            .in_("key_id", key_ids)
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )
        return list(events_res.data or [])

    events = await asyncio.to_thread(_fetch)
    by_domain: dict[str, int] = {}
    by_endpoint: dict[str, int] = {}
    daily: dict[str, int] = {}

    for ev in events:
        ep = str(ev.get("endpoint") or "unknown")
        dom = str(ev.get("domain") or "general")
        by_endpoint[ep] = by_endpoint.get(ep, 0) + 1
        by_domain[dom] = by_domain.get(dom, 0) + 1
        created = ev.get("created_at")
        if isinstance(created, str) and len(created) >= 10:
            day = created[:10]
            daily[day] = daily.get(day, 0) + 1

    return {
        "by_domain": by_domain,
        "by_endpoint": by_endpoint,
        "daily": daily,
        "total_events": len(events),
    }
