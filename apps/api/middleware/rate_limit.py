"""slowapi limiters for anonymous (IP) vs authenticated (user_id) traffic.

Both limiters point at the app's own Redis (settings.redis_url) via
storage_uri. Previously constructed with no storage_uri at all, which
made slowapi default to its in-memory MemoryStorage — not a degraded
fallback, the only mode this ever ran in — so under any multi-worker
deployment each worker enforced its own independent counter, making the
effective ceiling N_workers x the documented limit rather than one
global limit. Found during a full-codebase complexity trace.

slowapi's Limiter(storage_uri=...) does NOT connect eagerly — limits'
storage_from_string builds a lazy redis-py connection pool, so passing a
bad/unreachable URL doesn't raise at construction. The failure surfaces
later, on first real command (a request's rate-limit check, or this
module's own tests calling anonymous_limiter.reset() between tests).
_build_limiter() runs an explicit, short-timeout ping() up front instead
of relying on that lazy behavior, and falls back to a plain in-memory
Limiter — not slowapi's storage_uri-less default, an intentionally
separate MemoryStorage instance disconnected from Redis entirely — when
the ping fails, logged loudly. Same shape as agents/checkpointer.py's
Postgres-to-memory fallback: available over correct-but-crashable.
"""

import structlog
import redis as redis_sync
from core.config import settings
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

log = structlog.get_logger(__name__)

_rate_limit_backend = "unknown"


def get_rate_limit_backend() -> str:
    """'redis' | 'memory' | 'unknown' — surfaced on GET /health."""
    return _rate_limit_backend


def _redis_reachable() -> bool:
    try:
        client = redis_sync.Redis.from_url(
            settings.redis_url, socket_connect_timeout=1.5, socket_timeout=1.5
        )
        try:
            return bool(client.ping())
        finally:
            client.close()
    except Exception:
        return False


def _build_limiter(key_func) -> Limiter:
    global _rate_limit_backend
    if _redis_reachable():
        _rate_limit_backend = "redis"
        return Limiter(key_func=key_func, headers_enabled=True, storage_uri=settings.redis_url)
    log.error("rate_limiter_redis_unavailable_falling_back_to_memory", redis_url=settings.redis_url)
    _rate_limit_backend = "memory"
    return Limiter(key_func=key_func, headers_enabled=True)


anonymous_limiter = _build_limiter(get_remote_address)
authenticated_limiter = _build_limiter(
    lambda req: getattr(req.state, "user_id", None) or "__missing_user__"
)
# Note: slowapi's Limit.exempt_when is invoked without a Request; dual anonymous/authenticated
# quotas on /query use anonymous_limiter.limit(callable_limit, key_func=...) instead (see apply_query_rate_limit).


def query_rate_limit_key(request: Request) -> str:
    """Namespace keys so anonymous (per IP) and authenticated (per user) buckets stay independent."""
    uid = getattr(request.state, "user_id", None)
    if uid:
        return f"auth:{uid}"
    return f"anon:{get_remote_address(request)}"


def query_limit_provider(key: str) -> str:
    """slowapi LimitGroup requires a parameter named `key`; receives query_rate_limit_key(request)."""
    if key.startswith("auth:"):
        return "200/hour"
    return "30/hour"


def apply_query_rate_limit():
    """Dual policy on one backend: 30/hour per IP when anonymous, 200/hour per user when authed."""
    return anonymous_limiter.limit(query_limit_provider, key_func=query_rate_limit_key)
