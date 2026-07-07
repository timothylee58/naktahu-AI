---
name: new-endpoint
description: Scaffold a new FastAPI endpoint (router + service + tests + mounting) the NakTahu way. Use whenever adding an API route — encodes the two-mains mounting, slowapi signature, auth-tier choice, Supabase 503 guard, and the required test matrix.
---

# New API endpoint

## 1. Decide the auth tier first

| Need | Dependency | Rate limit |
|---|---|---|
| Public, works anonymous | `get_optional_user` (Optional[UserContext]) | `@apply_query_rate_limit()` (30/hr anon by IP, 200/hr authed by user) |
| Login required | `get_current_user` → 401 if absent | `@apply_query_rate_limit()` |
| Paid plan required | `require_plan("pro")` etc. (`free < student < pro < business`) | same |
| Consumes credits | `require_credits(n)` | same |
| Public read, no auth ever | none, but `@anonymous_limiter.limit("60/minute")` | explicit limiter |

## 2. Service layer — `apps/api/services/<name>.py`

Pure async functions taking `supabase_client` as an argument (never import a global client). Return plain dicts/values; raise nothing HTTP-specific. Credits mutations go through the `add_agent_credits` RPC; webhook-style handlers use claim-first idempotency copied from `services/billing.py` (`mark_event_processed` / `unmark_event_processed` — do not reorder to check-then-mark).

## 3. Router — `apps/api/routers/<name>.py`

Template (this exact shape avoids Traps #2–#4):

```python
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from middleware.rate_limit import apply_query_rate_limit
from services.auth import UserContext, get_optional_user
from services.<name> import do_thing

router = APIRouter(prefix="/api/v1/<name>", tags=["<name>"])


class ThingRequest(BaseModel):
    # EVERY field bounded — no unbounded str/list
    text: str = Field(..., min_length=1, max_length=2000)


@router.post("", status_code=201)
@apply_query_rate_limit()
async def post_thing(
    request: Request,
    response: Response,   # REQUIRED by slowapi even if unused — Trap #2
    body: ThingRequest,
    optional_user: Annotated[Optional[UserContext], Depends(get_optional_user)],
):
    if not request.app.state.supabase:   # degraded mode — Trap #4
        raise HTTPException(status_code=503, detail="<Feature> is temporarily unavailable")
    return await do_thing(request.app.state.supabase, ...)
```

Gotchas:
- `status_code=204` endpoints must also set `response_model=None` (Trap #3).
- Path params that are UUIDs: pre-validate with a regex and return 404 (not 422) on mismatch — see `routers/share.py`.
- Never log or store raw query text in Redis keys — hash first.

## 4. Mount in BOTH apps (Trap #1 — the one that ships broken silently)

- `apps/api/main.py`: add to the `from routers import ...` line and `app.include_router(<name>.router)`
- `apps/api/app/main.py`: same two edits.

Verify: `grep -n "<name>" apps/api/main.py apps/api/app/main.py` → both files hit.

## 5. Migration (if a new table)

New file `infra/supabase/migrations/NNN_<name>.sql`, NNN = current max + 1. Requirements: header comment explaining why; `ENABLE ROW LEVEL SECURITY` with explicit policies (public-readable tables need `CREATE POLICY ... FOR SELECT TO anon, authenticated USING (true)` — service-role writes bypass RLS); CHECK constraints kept in sync with `_VALID_DOMAINS` if domains are involved (Trap #6). It will NOT be auto-applied — tell the user to paste it into the Supabase SQL editor, and make the endpoint 503 cleanly until then.

## 6. Tests — `apps/api/tests/test_<name>.py`

Copy the fixture pattern from `tests/test_share.py` (mock Redis via `api_main.redis_ai.from_url`, mock Supabase via `api_main.create_client`, reset both limiters, `TestClient(api_main.app)`). Required matrix:

1. Happy path (status + response shape + what was inserted/queried)
2. Auth boundary: anonymous vs authenticated behaviour (or 401 where required)
3. Validation rejection → 422 (oversized field, missing field)
4. Degraded mode: `app.state.supabase = None` → 503
5. Rate-limit boundary if user-facing (loop to the limit, assert 429 on the next)

JWTs for tests: HS256 with `settings.jwt_secret`, `aud=settings.supabase_jwt_aud`. Non-ASCII fixtures: `"""...""".encode("utf-8")`, never `b"""..."""` (Trap #13).

## 7. Frontend wiring (if applicable)

Calls attach headers via the `auth-headers` helper; check `res.ok` and revert optimistic UI state on failure; all strings through `t('...')` with BM/EN/ZH keys added to `apps/web/src/lib/i18n/index.tsx`.

## 8. Finish

Run the `/ship` skill — do not hand-roll the commit/push/PR steps.
