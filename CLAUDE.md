# Naktahu AI — agent context

## Repository layout

- **`/`** — Next.js 16 frontend (`src/`, `app` router).
- **`apps/api/`** — FastAPI service: SSE **`POST /api/v1/query`**, **`GET/POST /api/v1/history`**, Supabase JWT auth, Redis session history, slowapi rate limits.

## API environment (`apps/api`)

| Variable | Purpose |
|----------|---------|
| `JWT_SECRET` | Supabase JWT secret (same value as in Supabase project JWT settings). |
| `SUPABASE_JWT_AUD` | JWT audience claim (default `authenticated`). |
| `REDIS_URL` | Redis for session history lists (`session_history:{user_id}`). |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_SERVICE_KEY` | Service role key for server-side inserts into `user_sessions`. |

## Phase checkpoints

- **Phase 2:** `/api/v1/query` SSE stream usable (token + done events).
- **Phase 3:** Auth (`services/auth.py`), dual query rate limits (`middleware/rate_limit.py`), history API (`routers/history.py`), startup Redis/Supabase checks (`main.py`).
- **Phase 4:** Next.js chat interface (`src/app/chat/page.tsx`), SSE streaming via `useSSEStream`, voice input via `useVoiceInput`, Framer Motion animations, bilingual BM/EN UI via `I18nProvider`.
- **Phase 5 (current):** Landing page (`src/app/(landing)/page.tsx`), TypewriterQuery animation, `HistorySidebar` + `HistoryPage`, Supabase SSR auth (`@supabase/ssr` — `lib/supabase/client.ts`, `server.ts`, `middleware.ts`), `AuthButton`, PWA manifest + service worker, `middleware.ts` session refresh.

## Commands

```bash
cd apps/api && python -m uvicorn main:app --reload --app-dir .
cd apps/api && python -m pytest tests/
```

See **`infra/supabase/AUTH_SETUP.md`** for provider configuration.
