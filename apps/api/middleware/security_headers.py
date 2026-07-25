"""Baseline defensive response headers.

This API only ever returns JSON/SSE (never renders HTML from user input),
so the highest-value XSS/injection surface is elsewhere — but these headers
are a cheap, zero-behavior-risk hardening baseline against a browser being
tricked into MIME-sniffing a response as something executable, or an error
page being framed for clickjacking.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response
