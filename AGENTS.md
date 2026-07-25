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
## Cursor Cloud specific instructions

NakTahu AI is a monorepo with two runnable services plus optional local Redis. Standard commands live in `README.md` and `package.json`; only the non-obvious, environment-specific caveats are captured here.

### Services

| Service | Dir | Dev run command | Port |
|---|---|---|---|
| Web (Next.js 15) | `apps/web` | `npm run dev` (from repo root or `apps/web`) | 3000 |
| API (FastAPI + LangGraph) | `apps/api` | `/workspace/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` (run **from `apps/api`**) | 8000 |
| Redis (optional cache/rate-limit) | — | `redis-server --daemonize yes --save "" --appendonly no` | 6379 |

### Non-obvious caveats

- **Python runs in a venv at `/workspace/.venv`.** The startup update script installs backend deps there (`apps/api` is installed editable). Use `/workspace/.venv/bin/uvicorn` / `/workspace/.venv/bin/pytest` — do not rely on a system `uvicorn`/`pytest`, and there is no `mise`/`pyenv` here (system Python is 3.12, which satisfies `requires-python >=3.11`).
- **Run the API with working directory `apps/api`.** The canonical app is `app.main:app`, but it also imports top-level packages (`core`, `services`, `middleware`), so the process cwd must be `apps/api` for imports to resolve. `pytest` relies on `pythonpath = ["."]` in `pyproject.toml`, so run it from `apps/api` too.
- **Two API entrypoints exist.** `apps/api/app/main.py` (`app.main:app`) is the canonical/deployed app and degrades gracefully when Redis/Supabase/ILMU are unavailable. `apps/api/main.py` is a legacy app that **requires Redis at startup**; the pytest suite imports it with Redis/Supabase mocked (`tests/conftest.py`). Always run/serve `app.main:app`.
- **The app boots and works without any real secrets.** Missing `ILMU_API_KEY` / `ANTHROPIC_API_KEY` / Supabase creds do not crash it — the pipeline (router→guard→rag→analyst→synthesiser) still runs and streams an SSE response, but returns a low-confidence clarification / fallback answer instead of real cited content. For real cited answers, provide `ILMU_API_KEY` + Supabase creds (and seed the vector DB via `scripts/ingest/`) as Cursor secrets, then mirror them into `apps/api/.env` and `apps/web/.env.local`.
- **Env files are gitignored and must exist locally.** `apps/api/.env` and `apps/web/.env.local` are not committed. Placeholder dev versions are created during setup; if missing, copy from `apps/api/.env.example` and `apps/web/.env.local.example`. The web rewrite proxies `/api/v1/*` to `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- **Frontend installs need `--legacy-peer-deps`** (React 19 peer ranges). CI uses `npm ci --legacy-peer-deps`; using a plain `npm install` rewrites cosmetic `package-lock.json` metadata (`devOptional`→`dev`) — prefer `npm ci` to avoid lockfile churn.
- **Redis and `python3.12-venv` are preinstalled in the VM snapshot** (apt system packages), so the update script does not reinstall them. Redis is optional (the API degrades gracefully); start it with the command above if you want caching/rate-limiting active. Docker is **not** installed — do not use `infra/docker-compose.yml`; run the services directly instead.

### Checks

- Web: `npm run typecheck` and `npm run lint` (repo root).
- API: `pytest tests/ -q` from `apps/api` using the venv (`/workspace/.venv/bin/pytest`).
