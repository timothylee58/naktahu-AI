from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/ignored", auto_error=False)

# Supabase Auth includes app_metadata in the JWT automatically once set via
# the admin API (services/billing.py, on checkout.session.completed). No
# separate plan/subscriptions table needed — the JWT claim is the source of
# truth, refreshed client-side after checkout completes.
VALID_PLANS = {"free", "student", "pro", "business"}


@dataclass(frozen=True)
class UserContext:
    user_id: str
    is_anonymous: bool
    plan: str = "free"
    email: Optional[str] = None


def _decode_supabase_jwt(token: str) -> Optional[UserContext]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_aud,
        )
    except ExpiredSignatureError:
        return None
    except InvalidTokenError:
        return None
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        return None

    plan = "free"
    app_metadata = payload.get("app_metadata")
    if isinstance(app_metadata, dict):
        raw_plan = app_metadata.get("plan")
        if isinstance(raw_plan, str) and raw_plan in VALID_PLANS:
            plan = raw_plan

    email = payload.get("email")
    if not isinstance(email, str):
        email = None

    return UserContext(user_id=sub, is_anonymous=False, plan=plan, email=email)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> UserContext:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    ctx = _decode_supabase_jwt(token)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


async def get_optional_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[UserContext]:
    if not token:
        return None
    return _decode_supabase_jwt(token)
