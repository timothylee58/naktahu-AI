"""HTTP RED metrics (rate, errors, duration) for every request.

Uses the matched route *template* (e.g. /api/v1/query/{session_id}), not the
raw path, for the route label — using raw paths would blow up label
cardinality with every distinct session/user ID that ever hits the API.
"""

import time
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.prometheus_metrics import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path == "/metrics":
            # Don't instrument the metrics endpoint itself — avoids
            # self-referential noise on every scrape.
            return await call_next(request)

        # request.scope["route"] is only populated by FastAPI's routing AFTER
        # the request has been dispatched to a handler — it doesn't exist yet
        # at this point, so the in-progress gauge can only be labeled by
        # method until call_next() returns.
        method = request.method
        http_requests_in_progress.labels(method=method).inc()
        start = time.monotonic()
        status_code = "500"  # default: overwritten below if call_next succeeds
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        finally:
            # An unhandled exception from call_next skips straight past a
            # try-body return, but this finally still runs before the
            # exception propagates — so a failed request that never reaches
            # the "return response" line above is recorded here as a 500,
            # instead of vanishing from RED metrics entirely.
            elapsed = time.monotonic() - start
            http_requests_in_progress.labels(method=method).dec()
            route = request.scope.get("route")
            route_label = route.path if route is not None else "unmatched"
            http_request_duration_seconds.labels(method=method, route=route_label).observe(elapsed)
            http_requests_total.labels(
                method=method,
                route=route_label,
                status_code=status_code,
            ).inc()
