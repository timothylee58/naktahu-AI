"""Attach optional Supabase user id to request.state before rate limiting."""

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.config import settings


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    return auth[7:].strip() or None


class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = _bearer_token(request)
        user_id: str | None = None
        if token:
            try:
                payload = jwt.decode(
                    token,
                    settings.jwt_secret,
                    algorithms=["HS256"],
                    audience=settings.supabase_jwt_aud,
                )
                sub = payload.get("sub")
                if isinstance(sub, str) and sub:
                    user_id = sub
            except (ExpiredSignatureError, InvalidTokenError):
                user_id = None
        request.state.user_id = user_id
        request.state.is_anonymous = user_id is None
        return await call_next(request)
