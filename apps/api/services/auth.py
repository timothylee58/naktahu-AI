from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/ignored", auto_error=False)


@dataclass(frozen=True)
class UserContext:
    user_id: str
    is_anonymous: bool


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
    return UserContext(user_id=sub, is_anonymous=False)


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
