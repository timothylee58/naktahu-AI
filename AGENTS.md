# AGENTS.md

## Purpose
This document is a fast onboarding and interview-prep guide for the `timothylee58/naktahu-AI` codebase.

## What this repository is
NakTahu AI is a Malaysian-focused AI answer engine that returns cited answers from official sources, with streaming responses and multilingual support.

## Monorepo structure
- `apps/web` — Next.js 15 frontend (TypeScript, Tailwind, Framer Motion, Supabase client)
- `apps/api` — FastAPI backend with LangGraph-based AI pipeline
- `packages/shared-types` — shared TypeScript types
- `scripts/ingest` — ingestion/chunking/upload scripts for knowledge data
- `infra` — local infrastructure helpers (e.g., Docker Compose)
- `.github/workflows` — CI/CD automation

## Key technologies
### Frontend
- Next.js 15 (App Router)
- TypeScript (strict)
- Tailwind CSS
- Framer Motion
- Supabase JS/SSR clients

### Backend
- Python 3.11+
- FastAPI
- LangGraph + LangChain Core
- ILMU API (primary model provider)
- Anthropic Claude Sonnet fallback for synthesis
- Supabase + pgvector for retrieval
- Redis for cache/rate-limits/history
- slowapi for rate limiting

### DevOps
- GitHub Actions for CI (typecheck, build, pytest)
- Netlify deployment for web
- Railway deployment for API

## How code is organized
### Backend flow (`apps/api/app`)
- `main.py` — FastAPI app entrypoint and middleware wiring
- `routers/` — HTTP routes (query/history)
- `agents/` — LangGraph nodes:
  - `router_node.py` (intent/language/domain routing)
  - `rag_node.py` (vector retrieval + cache)
  - `analyst_node.py` (citation/confidence scoring)
  - `synthesiser_node.py` (streaming final answer)
- `services/` — external integrations (LLM clients, vector store, etc.)
- `middleware/` — auth/rate-limit related behavior
- `models/` — request/response/state models

### Frontend flow (`apps/web/src`)
- `app/` — route segments/pages
- `components/` — UI components (search input, citation UI, etc.)
- `lib/` — client utilities (i18n, API helpers, streaming hooks)

## Runtime workflow (end-to-end)
1. User submits query in the web app.
2. Frontend opens SSE stream to `POST /api/v1/query`.
3. Backend runs LangGraph pipeline:
   1) `router_node` classifies language/domain/intent
   2) `rag_node` retrieves top chunks from Supabase (or cache hit)
   3) `analyst_node` computes confidence and maps citations
   4) `synthesiser_node` streams answer tokens
4. API emits SSE events: `token`, `citation`, `metadata`, `done` (or `error`).
5. Frontend renders tokens progressively and displays citation chips.

## Data and trust workflow
- Retrieval is grounded in indexed sources (Supabase pgvector).
- Citations are emitted as explicit stream events.
- Confidence scoring gates low-confidence outputs.
- Cache reduces repeated retrieval cost and latency.

## Auth and limits workflow
- Optional auth for query endpoint, required auth for history endpoint.
- Anonymous users: stricter rate limits.
- Authenticated users: higher quota.
- Redis stores short-term result cache and recent session history.

## CI/CD workflow
- PRs to `main`: TypeScript typecheck, Next.js build, Python tests.
- Push to `main`: deploy web, then deploy API.

## Interview-ready talking points
- **Agentic RAG design**: clear separation between routing, retrieval, trust scoring, and synthesis.
- **Streaming UX**: SSE token streaming for low perceived latency.
- **Production controls**: auth, rate limiting, retries/fallback provider path.
- **Monorepo discipline**: split frontend/backend/shared types with centralized CI.
- **Source-grounded answers**: citations and confidence metadata as trust signals.

## Local development quick commands
- Root: `npm ci --legacy-peer-deps`
- Web dev: `npm run dev --workspace=apps/web`
- Web typecheck: `npm run typecheck`
- API setup: `cd apps/api && pip install -e ".[dev]"`
- API run: `cd apps/api && uvicorn app.main:app --reload`
- API tests: `cd apps/api && pytest tests/ -q`
