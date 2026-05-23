"""slowapi limiters for anonymous (IP) vs authenticated (user_id) traffic."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

anonymous_limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
)

authenticated_limiter = Limiter(
    key_func=lambda req: getattr(req.state, "user_id", None) or "__missing_user__",
    headers_enabled=True,
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
