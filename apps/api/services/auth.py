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
VALID_PLANS = {"free", "student", "pro", "business", "investor"}
ADMIN_ROLES = frozenset({"primary_admin", "secondary_admin"})

# Parallel entitlements — capability flags that are NOT rungs on the plan
# ladder (see middleware/plan_gate._PLAN_RANK). An entitlement is granted
# either by app_metadata.entitlements (a list of strings) or implicitly by
# holding the same-named plan. "investor" is the first: a VC firm on the
# investor plan is a different market segment from a business-plan SME, so
# neither inherits the other's features by ordinal comparison.
VALID_ENTITLEMENTS = frozenset({"investor"})


@dataclass(frozen=True)
class UserContext:
    user_id: str
    is_anonymous: bool
    plan: str = "free"
    email: Optional[str] = None
    role: Optional[str] = None
    entitlements: tuple[str, ...] = ()


def effective_plan(plan: str, role: Optional[str]) -> str:
    """Admins always resolve to business tier for feature gates."""
    if role in ADMIN_ROLES:
        return "business"
    return plan


def is_admin_role(role: Optional[str]) -> bool:
    return role in ADMIN_ROLES if role else False


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
    role: Optional[str] = None
    app_metadata = payload.get("app_metadata")
    if isinstance(app_metadata, dict):
        raw_plan = app_metadata.get("plan")
        if isinstance(raw_plan, str) and raw_plan in VALID_PLANS:
            plan = raw_plan
        raw_role = app_metadata.get("role")
        if isinstance(raw_role, str) and raw_role in ADMIN_ROLES:
            role = raw_role

    # Entitlements are resolved from the RAW plan, before effective_plan()
    # collapses admins to "business" — otherwise an admin on the investor
    # plan would silently lose the investor entitlement.
    granted: set[str] = set()
    if plan in VALID_ENTITLEMENTS:
        granted.add(plan)
    if isinstance(app_metadata, dict):
        raw_entitlements = app_metadata.get("entitlements")
        if isinstance(raw_entitlements, list):
            granted.update(
                e for e in raw_entitlements
                if isinstance(e, str) and e in VALID_ENTITLEMENTS
            )

    plan = effective_plan(plan, role)

    email = payload.get("email")
    if not isinstance(email, str):
        email = None

    return UserContext(
        user_id=sub,
        is_anonymous=False,
        plan=plan,
        email=email,
        role=role,
        entitlements=tuple(sorted(granted)),
    )


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
