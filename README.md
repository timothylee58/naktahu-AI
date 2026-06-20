# NakTahu AI

> **Ilmu tempatan, jawapan seketika.**
----

NakTahu AI is a Malaysian-focused trilingual AI answer engine that delivers cited, government-sourced answers in Bahasa Malaysia, English and Mandarin.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          User (Browser)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  apps/web  (Next.js 15, Vercel)                 │
│                                                                 │
│   SearchBar → useSSEStream hook → CitationChip × 1–3            │
│   Navbar (language toggle) ← i18n (bm.json / en.json)           │
└────────────────────────────┬────────────────────────────────────┘
                             │ SSE  /api/v1/query
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  apps/api  (FastAPI, Render)                    │
│                                                                 │
│   ┌──────────┐    ┌─────────┐    ┌───────────┐    ┌─────────┐   │
│   │  router  │───▶│  rag   │───▶│  analyst  │───▶│synth    │  │
│   │  _node   │    │  _node  │    │  _node    │    │iser     │   │
│   │  (ILMU)  │    │pgvector │    │confidence │    │(ILMU+   │   │
│   └──────────┘    └────┬────┘    └───────────┘    │fallbk)  │   │
│                        │                           └────┬───┘   │
│                   Redis cache                      SSE stream   │
└────────────────────────┼────────────────────────────────┼───────┘
                         │                                │
              ┌──────────▼──────────┐         ┌──────────▼──────────┐
              │  Supabase + pgvector│         │   Browser via SSE   │
              │  (document_chunks)  │         │  event: token/done  │
              └─────────────────────┘         └─────────────────────┘
```

---

## Monorepo layout

```
naktahu-AI/
├── apps/
│   ├── web/          — Next.js 15 App Router frontend (Vercel)
│   └── api/          — FastAPI backend with LangGraph agent (Render)
├── packages/
│   └── shared-types/ — Shared TypeScript interfaces
├── scripts/
│   └── ingest/       — Document ingestion pipeline
├── infra/
│   └── docker-compose.yml
└── .github/
    └── workflows/
        ├── ci.yml    — typecheck + pytest on PR
        └── deploy.yml — Vercel + Render on main merge
```

---

## Quick start

### Prerequisites

- Node.js 22+
- Python 3.11+
- Docker & Docker Compose

### 1. Clone and install

```bash
git clone https://github.com/timothylee58/naktahu-AI.git
cd naktahu-AI

# Frontend
npm install --workspace=apps/web --legacy-peer-deps

# Backend
(cd apps/api && pip install -e ".[dev]")
```

### 2. Configure environment variables

```bash
# Web
cp apps/web/.env.local.example apps/web/.env.local
# Edit apps/web/.env.local with your values

# API
cp apps/api/.env.example apps/api/.env
# Edit apps/api/.env with your values
```

### 3. Run with Docker Compose

```bash
docker compose -f infra/docker-compose.yml up
```

This starts:
- **API** at `http://localhost:8000`
- **Redis** at `localhost:6379`

### 4. Run the frontend

```bash
cd apps/web
npm run dev
```

Frontend available at `http://localhost:3000`.

---

## Environment variable reference

### Web (`apps/web/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous public key |

### API (`apps/api/.env`)

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key (synthesis fallback) |
| `ILMU_API_KEY` | ILMU API key (primary LLM + embeddings) |
| `ILMU_BASE_URL` | ILMU API base URL |
| `ILMU_CHAT_MODEL` | ILMU chat model name |
| `ILMU_EMBEDDING_MODEL` | ILMU embedding model name |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (server-only, never expose) |
| `REDIS_URL` | Redis connection URL (e.g. `redis://localhost:6379`) |
| `JWT_SECRET` | Secret for validating Supabase JWTs |
| `SENTRY_DSN` | Sentry DSN for error tracking (optional) |
| `LANGSMITH_API_KEY` | LangSmith API key for tracing |
| `LANGSMITH_PROJECT` | LangSmith project name (`naktahu-ai`) |

---

## CI/CD

| Trigger | Action |
|---|---|
| PR to `main` | `tsc --noEmit` + `pytest` |
| Push to `main` | Deploy `apps/web` → Vercel, trigger Render deploy hook for `apps/api` |

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript strict, Tailwind CSS, shadcn/ui, Framer Motion |
| Backend | Python 3.11, FastAPI, LangGraph 0.2+, LangChain Core |
| LLM | ILMU API (primary) + `claude-sonnet-4-20250514` (synthesis fallback) |
| Embeddings | ILMU API (`ilmu-embedding`) |
| Vector DB | Supabase pgvector |
| Cache | Redis (Render) |
| Auth | Supabase Auth (email + Google OAuth) |
