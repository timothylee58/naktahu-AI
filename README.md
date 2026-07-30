# NakTahu AI

> **Ilmu tempatan, jawapan seketika.**
----

NakTahu AI is a Malaysian-focused, trilingual AI answer engine (Bahasa Malaysia, English, Mandarin) that delivers cited, government-sourced answers to questions about Malaysian public services, law, education, finance, and healthcare. Beyond chat, it's an agentic platform: a set of vertical AI agents for grant matching, compliance drafting, immigration, health triage, exam prep, investor due diligence, and parliamentary transparency, plus a metered Developer/Knowledge API for external integrators.

---

## Features

### Core answer engine
- **Trilingual answers** — BM, EN, and ZH (Mandarin) in a single interface, with automatic query-language detection (deterministic Unicode-range detection for CJK script, LLM classification otherwise).
- **Retrieval-augmented, cited answers** — every response surfaces 1–3 citation chips linked to real, verified `gov.my`-family sources. If no verified source exists for a claim, the citation is omitted — never fabricated.
- **Hybrid search** — Supabase pgvector combining cosine similarity and BM25 keyword search over an ingested government-document corpus.
- **Confidence gating** — low-confidence retrievals trigger a clarification prompt instead of a guessed answer.
- **Freshness-aware retrieval** — chunks carry effective-date metadata so superseded rules/figures (e.g. last year's withdrawal cap) are excluded from citation even if they'd otherwise match well.
- **Streamed responses** — Server-Sent Events end-to-end, token-by-token.
- **Voice input** — dictate queries via the Web Speech API (Chrome/Edge; `ms-MY`, `en-MY`, `zh-CN`).
- **Prompt-injection resistant** — layered input/output safety scanning on both user queries and ingested content, independent of and in addition to the LLM's own instruction-following.

### Vertical agents
A shared LangGraph-based agent framework backs several purpose-built assistants, each plan-gated or credit-metered:

| Agent | What it does |
|---|---|
| **Eligibility Agent** | Multi-turn business grant-eligibility matching — conversational intake, hybrid grant retrieval, scoring with near-miss detection, and grant-stacking compatibility analysis (which programmes can legally be combined). |
| **Grant Draft Generator** | Given a selected grant and business profile, drafts an executive summary, use-of-funds narrative, a financial-projection *template* (explicitly never presented as real figures), and a required-document checklist; exports to PDF or Word. |
| **Compliance Drafter** | Multi-domain compliance report generation with a human-in-the-loop approval step before the final document is produced. |
| **SME Compliance Navigator (PatuhiKu)** | Cross-references a business profile against tax (LHDN), employment (EPF/SOCSO/EIS), and company (SSM) obligations in parallel. |
| **Immigration Navigator** | Conversational visa/permit intake grounded in immigration-domain retrieval. |
| **Health Triage** | Bahasa Malaysia symptom intake with severity assessment and public healthcare facility recommendations. |
| **Study Agent** | Upload an SPM past paper and get retrieval-grounded explanations per question. |
| **Research Synthesiser** | Parallel multi-domain retrieval and synthesis for broader research-style questions. |
| **Investor Intelligence** | Matches an investor's thesis (sector, stage, ticket size) against active grant programmes and Budget-cycle co-investment mandates. |
| **Deadline Monitor** | Tracks regulatory and grant-application deadlines, with configurable advance alerts. |
| **Parliament Watch** | MP profile, voting record, and constituency lookup, backed by a Hansard ingestion pipeline. |

### Platform
- **Developer / Knowledge API** — a separate, API-key-authenticated surface (`/api/v1/public`, `/api/v1/developer`) for external integrators: single- and multi-domain query endpoints, streaming, self-hosted OpenAPI docs, and per-key usage tracking.
- **Shareable answers** — generate a permalink for any answer.
- **Session history** — authenticated users get persistent query history.
- **Redis-backed caching** — repeated queries skip retrieval entirely (content-hash keyed, TTL-bound).
- **Tiered rate limiting** — anonymous and authenticated users get different request budgets; the Developer API is independently metered per key.
- **Plan-based access** — free / student / pro / business tiers, plus an independent "investor" entitlement for the Investor Intelligence product — read from the user's Supabase session, not a separate subscriptions table.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          User (Browser)                         │
└────────────────────────────┬────────────────────────────────────┘
                              │ HTTPS
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                apps/web  (Next.js 15, Netlify)                  │
│                                                                   │
│   Chat UI → useSSEStream hook → CitationChip × 1–3               │
│   Vertical-agent UIs (grants, compliance, career, …)             │
│   i18n (BM / EN / ZH) ← Navbar language toggle                  │
└────────────────────────────┬────────────────────────────────────┘
                              │ SSE  /api/v1/query, /api/v1/agents/*
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                apps/api  (FastAPI, Railway)                     │
│                                                                   │
│   Core RAG pipeline (LangGraph):                                 │
│   ┌────────┐   ┌───────┐   ┌────────┐   ┌─────────┐   ┌────────┐│
│   │ router │──▶│ guard │──▶│  rag   │──▶│ analyst │──▶│synth-  ││
│   │ _node  │   │ _node │   │ _node  │   │ _node   │   │esiser  ││
│   │ (ILMU) │   │safety │   │pgvector│   │confidence│  │(ILMU + ││
│   └────────┘   └───────┘   └───┬────┘   └─────────┘   │Claude  ││
│                                 │                       │fallbk) ││
│                            Redis cache             SSE stream    ││
│                                                        └────┬───┘│
│   Vertical agent graphs (own LangGraph pipelines, share      │    │
│   the router/RAG/tool layer): grant, compliance, immigration,│    │
│   health, study, investor, deadline, parliament agents       │    │
└─────────────────┬──────────────────────────────────────────┼────┘
                   │                                          │
        ┌──────────▼──────────┐                    ┌──────────▼──────────┐
        │  Supabase + pgvector│                    │   Browser via SSE   │
        │  (document_chunks,  │                    │  event: token/done  │
        │   agent/domain      │                    └─────────────────────┘
        │   tables)           │
        └─────────────────────┘
```

---

## Monorepo layout

```
naktahu-AI/
├── apps/
│   ├── web/                    — Next.js 15 App Router frontend (Netlify)
│   │   └── src/app/            — chat, agents, career, developer, pricing,
│   │                              history, auth, about, faq, privacy
│   └── api/                    — FastAPI backend (Railway)
│       ├── main.py             — root app (imported by the test suite)
│       ├── app/main.py         — deploy app (what Railway actually runs)
│       ├── app/agents/         — core RAG pipeline + vertical agent packages
│       ├── app/orchestration/  — agent registry, routing, circuit breakers
│       ├── routers/            — shared HTTP routers (query, billing, share,
│       │                          developer, public API, history, feedback)
│       ├── app/routers/        — deploy-only routers (agents, health,
│       │                          parliament, investor, transcribe, session)
│       ├── services/           — auth, billing, api key/credit management
│       ├── middleware/         — rate limiting, plan gating, sanitisation
│       └── scripts/            — document + Hansard ingestion pipelines
├── infra/
│   ├── supabase/migrations/    — versioned SQL schema (30+ files)
│   └── docker-compose.yml
└── .github/workflows/
    ├── ci.yml              — typecheck, pytest, and an eval-quality gate on PRs
    ├── deploy.yml          — Netlify deploy on push to main
    ├── lighthouse.yml      — Lighthouse CI (PWA score gate)
    └── ping-supabase.yml   — keeps the free-tier Supabase project awake
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

### 5. Apply database migrations

Migrations under `infra/supabase/migrations/` are versioned SQL, applied manually via the Supabase SQL editor (or the Supabase CLI) — nothing applies them automatically. Apply them in numeric order.

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
| `ANTHROPIC_API_KEY` | Anthropic API key (synthesis fallback only) |
| `ILMU_API_KEY` | ILMU API key (primary LLM + embeddings) |
| `ILMU_BASE_URL` | ILMU API base URL |
| `ILMU_CHAT_MODEL` | ILMU chat model name |
| `ILMU_EMBEDDING_MODEL` | ILMU embedding model name |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key — **server-only, never exposed to the frontend** |
| `REDIS_URL` | Redis connection URL |
| `JWT_SECRET` | Secret for validating Supabase JWTs |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe billing (subscriptions + credit packs) |
| `HITPAY_API_KEY` / `HITPAY_WEBHOOK_SALT` | HitPay billing (FPX/DuitNow credit packs) |
| `SENTRY_DSN` | Sentry DSN for error tracking (optional) |
| `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | LLM tracing (optional) |

See `apps/api/core/config.py` for the complete, authoritative list.

---

## CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | PR to `main`, push to `main`/`claude/**` | TypeScript typecheck, Next.js build, pytest, and an automated eval-quality gate (faithfulness + temporal-accuracy scoring) that blocks deploy on regression |
| `deploy.yml` | Push to `main` | Deploys `apps/web` to Netlify. `apps/api` deploys via Railway's own build hook. |
| `lighthouse.yml` | Push to `main`, manual dispatch | Lighthouse CI audit, gated on a minimum PWA score |
| `ping-supabase.yml` | Mon + Thu 9am UTC | Keeps the Supabase free-tier project from auto-pausing |

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), React 19, TypeScript (strict), Tailwind CSS 4, Framer Motion, Web Speech API |
| Backend | Python 3.11+, FastAPI, LangGraph, LangChain Core |
| LLM | ILMU API (primary) + Anthropic Claude (synthesis fallback only) |
| Embeddings | ILMU API, with an OpenAI-compatible fallback |
| Vector DB | Supabase pgvector — hybrid cosine + BM25 search |
| Cache | Redis |
| Auth | Supabase Auth — plan/entitlements read from the JWT session, no separate subscriptions table |
| Payments | Stripe (subscriptions + credit packs) and HitPay (FPX/DuitNow credit packs) |
| Observability | Sentry, LangSmith, Prometheus metrics, structured logging |

---

## Contributing

This repo has an unusually detailed internal operating manual (`CLAUDE.md`) covering conventions, deployment quirks, and a running list of mistakes that have already cost real debugging time — read it before your first PR. A few of the load-bearing rules:

- **Two FastAPI apps exist** — a root app the test suite imports, and a nested `app/` package Railway actually deploys. Every new route must be mounted in both.
- **Citations are never fabricated.** Only real, verified government source URLs are ever shown; if none exists, the citation is omitted.
- **The confidence gate is a trust layer, not decoration.** Low-confidence retrieval always triggers a clarification response, never a best-effort guess.
- **Secrets are referenced by env-var name only** — never hardcoded, committed, or logged, and the Supabase service-role key never reaches the frontend in any form.
- **LLM provider order is a deliberate design decision**, not something to change casually — ILMU is primary, Claude is a synthesis-only fallback.

Pull requests run through the same CI gate described above — typecheck, tests, and an automated answer-quality eval — before merge.
