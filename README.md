# NakTahu AI

> **Ilmu tempatan, jawapan seketika.**
----

NakTahu AI is a Malaysian-focused trilingual AI answer engine that delivers cited, government-sourced answers in Bahasa Malaysia, English and Mandarin.

---

## Features

- **Trilingual answers** — BM, EN, and ZH (Mandarin) in a single interface.
- **Voice input** — users can dictate queries using the Web Speech API. Supported languages: Bahasa Malaysia (`ms-MY`), English (`en-US`), and Mandarin (`zh-CN`). Voice input requires Chrome or Edge; other browsers lack the necessary Google speech API keys.
- **Deterministic CJK language detection** — the `router_node` performs a Unicode range check for CJK script before calling the LLM. Any query containing CJK characters is tagged `"zh"` immediately, bypassing the LLM classifier and guaranteeing a Mandarin response.
- **Synthesiser language enforcement** — the `synthesiser_node` prepends a language-specific instruction (BM / EN / ZH) to the system prompt so the response language always matches the detected query language, regardless of retrieved document language.
- **Cited answers** — every response surfaces 1–3 citation chips linked to official Malaysian government sources.
- **Guided career assessment** — the `/career` page walks users through a step-by-step assessment to match their profile against relevant career pathways.
- **Redis-backed caching** — repeated queries skip the RAG and analyst nodes (1-hour TTL).
- **Rate limiting** — anonymous users 30 req/hour, authenticated users 200 req/hour.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          User (Browser)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  apps/web  (Next.js 15, Netlify)                 │
│                                                                 │
│   SearchBar → useSSEStream hook → CitationChip × 1–3            │
│   Navbar (language toggle) ← i18n (index.tsx: BM / EN / ZH)     │
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
│   ├── web/          — Next.js 15 App Router frontend (Netlify)
│   └── api/          — FastAPI backend with LangGraph agent (Render)
├── packages/
│   └── shared-types/ — Shared TypeScript interfaces
├── scripts/
│   └── ingest/       — Document ingestion pipeline
├── infra/
│   └── docker-compose.yml
└── .github/
    └── workflows/
        ├── ci.yml              — typecheck + pytest on PR
        ├── deploy.yml          — Netlify + Render on main merge
        └── ping-supabase.yml   — cron (Mon + Thu 9 AM UTC) to keep the Supabase free-tier project alive
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
| Push to `main` | Deploy `apps/web` → Netlify, trigger Render deploy hook for `apps/api` |
| Mon + Thu 9 AM UTC | `ping-supabase.yml` — wakes the Supabase free-tier project to prevent auto-pause |

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript strict, Tailwind CSS, shadcn/ui, Framer Motion, Web Speech API (voice input) |
| Backend | Python 3.11, FastAPI, LangGraph 0.2+, LangChain Core |
| LLM | ILMU API (primary) + `claude-sonnet-4-20250514` (synthesis fallback) |
| Embeddings | ILMU API (`ilmu-embedding`) |
| Vector DB | Supabase pgvector |
| Cache | Redis (Render) |
| Auth | Supabase Auth (email + Google OAuth) |
