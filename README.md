# NakTahu AI

> **Ilmu tempatan, jawapan seketika.**
----

NakTahu AI is a Malaysian-focused, trilingual AI answer engine (Bahasa Malaysia, English, Mandarin) that delivers cited, government-sourced answers to questions about Malaysian public services, law, education, finance, and healthcare. Beyond chat, it's an agentic platform: a set of vertical AI agents for grant matching, compliance drafting, retrenchment guidance, immigration, health triage, exam prep, investor due diligence, and parliamentary transparency; a crowdsourced live-status tool for local eateries (Warung Watch); and a metered Developer/Knowledge API for external integrators.

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
| **Grant Finder** (backend: Eligibility Agent) | Multi-turn business grant-eligibility matching — conversational intake (business type, sector, revenue, headcount, Bumiputera status), hybrid retrieval against a seeded, source-cited grant database (Cradle Fund, MDEC, SME Corp, HRD Corp and others), scoring with near-miss detection, and a grant-stacking compatibility matrix (which programmes can legally be combined). Statutory tax-incentive matching (Pioneer Status, ITA, RA) is a known, deliberately unbuilt gap — no verified source corpus for it exists yet, so it's not fabricated. |
| **Grant Draft Generator** | Given a selected grant and business profile, drafts an executive summary, use-of-funds narrative, a financial-projection *template* (explicitly never presented as real figures), and a required-document checklist; exports to PDF or Word. |
| **Compliance Drafter** | Multi-domain compliance report generation with a human-in-the-loop approval step before the final PDF is produced. |
| **SME Compliance Navigator (PatuhiKu)** | Cross-references a business profile against tax (LHDN), employment (EPF/SOCSO/EIS), and company (SSM) obligations in parallel. |
| **Immigration Navigator** | Conversational visa/permit intake grounded in immigration-domain retrieval. |
| **Retrenchment Navigator** | Guided retrenchment options — EIS unemployment-claim eligibility, statutory termination-benefit calculation (deterministic Employment Act arithmetic, never LLM-guessed), and a next-steps checklist. Free tier, 0 credits. |
| **Health Triage** | Bahasa Malaysia symptom intake with severity assessment, public healthcare facility recommendations, and an on-demand PDF export of the triage summary. |
| **Study Agent** | Upload an SPM past paper and get retrieval-grounded explanations per question. |
| **Research Synthesiser** | Parallel multi-domain retrieval and synthesis for broader research-style questions. |
| **Investor Intelligence** | Matches an investor's thesis (sector, stage, ticket size) against active grant programmes and Budget-cycle co-investment mandates. |
| **Deadline Monitor** | Tracks regulatory and grant-application deadlines, with configurable advance alerts (runs nightly via GitHub Actions, not a Railway cron service). |
| **Parliament Watch** | MP profile, voting record, and constituency lookup, backed by a Hansard ingestion pipeline. |

A rule-based query→agent matcher (no LLM call) surfaces a relevant agent inline while typing in the main chat box, and every agent turn is logged to a per-user, per-agent run history surfaced under **History** — independent of the chat-history plan gate, since several agents (Health Triage, Retrenchment Navigator) are free-tier.

### Warung Watch
A standalone crowdsourced "how busy is it right now" tool for Malaysian warungs/kopitiams/food stalls — deliberately outside the RAG pipeline, since live crowd status has no citable government source and has its own freshness window instead. Users check a place's current status (search-and-match against reported names), submit their own status report, and optionally attach a price report for a specific menu item; price reports render as a real trend chart (recharts) once a warung has enough data points — never a fabricated sample series. A "nearby places" search assist calls the real Google Places API (New) Nearby Search endpoint when `GOOGLE_PLACES_API_KEY` is configured (degrades to a Maps-link-only view otherwise); Google's Popular Times data is explicitly *not* used, since it isn't exposed via any official, ToS-compliant API.

### Platform
- **Developer / Knowledge API** — a separate, API-key-authenticated surface (`/api/v1/public`, `/api/v1/developer`) for external integrators: single- and multi-domain query endpoints, streaming, self-hosted OpenAPI docs, and per-key usage tracking.
- **Shareable answers** — generate a permalink for any answer.
- **Session history** — authenticated users get persistent query history (pro plan), plus a separate, non-plan-gated agent-run history (drafts, checklists, eligibility results) for any signed-in user.
- **Interactive citation cards** — hover or tap a citation chip for the full source title, a colour-coded confidence rating, staleness flag, and the direct source link, instead of only a truncated inline chip.
- **Document export** — Compliance Drafter, Grant Draft Generator, and Health Triage can each export their output to PDF (Grant Draft Generator also supports Word), rendered server-side (WeasyPrint / python-docx) and served via a signed, time-limited Supabase Storage URL.
- **Optional cross-encoder-style re-ranking** — a second retrieval pass over `hybrid_search`'s candidate pool, re-scoring (query, chunk) pairs together via the same ILMU chat client rather than a new provider. Off by default (`RERANK_ENABLED`) pending an eval-set comparison; degrades to the unranked order on any failure.
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
│   │                              history, warung-watch, auth, about, faq, privacy
│   └── api/                    — FastAPI backend (Railway)
│       ├── main.py             — root app (imported by the test suite)
│       ├── app/main.py         — deploy app (what Railway actually runs)
│       ├── app/agents/         — core RAG pipeline + vertical agent packages
│       ├── app/orchestration/  — agent registry, routing, circuit breakers
│       ├── routers/            — shared HTTP routers (query, billing, share,
│       │                          developer, public API, history, feedback,
│       │                          warung-watch)
│       ├── app/routers/        — deploy-only routers (agents, health,
│       │                          parliament, investor, transcribe, session)
│       ├── services/           — auth, billing, api key/credit management
│       ├── middleware/         — rate limiting, plan gating, sanitisation
│       └── scripts/            — document + Hansard ingestion pipelines
├── packages/
│   └── shared-types/           — TypeScript types shared across the web workspace
├── infra/
│   ├── supabase/migrations/    — versioned SQL schema (30+ files)
│   └── docker-compose.yml
└── .github/workflows/
    ├── ci.yml                 — typecheck, pytest, and an eval-quality gate on PRs
    ├── deploy.yml             — Netlify deploy on push to main (apps/api deploys via Railway's own GitHub build hook, not this workflow)
    ├── deadline-monitor.yml   — nightly deadline-alert run, on a GitHub runner (not Railway cron — see the workflow's own comment for why)
    ├── ingest-sources.yml     — weekly document-ingestion run against scripts/sources.py's registered sources
    ├── lighthouse.yml         — Lighthouse CI (PWA score gate)
    └── ping-supabase.yml      — keeps the free-tier Supabase project awake
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
| `NEXT_PUBLIC_SENTRY_DSN` | Sentry DSN for client-side error tracking (optional — a placeholder/invalid value is validated and ignored, not just an unset check) |

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
| `GOOGLE_PLACES_API_KEY` | Enables Warung Watch's real nearby-place search assist (Places API New, Nearby Search). Optional — degrades to a Maps-link-only view when unset. |
| `GOOGLE_SPEECH_CREDENTIALS_JSON` / `GOOGLE_SPEECH_PROJECT_ID` / `GOOGLE_SPEECH_LOCATION` | Google Speech-to-Text V2, cross-browser voice-input fallback. Optional — the frontend falls back to the browser's own Web Speech API when unset. |
| `RERANK_ENABLED` | Turns on the optional cross-encoder-style re-ranking pass over hybrid-search results (default `false`) |

Most are validated via `apps/api/core/config.py`'s `Settings` object — but not all: `GOOGLE_PLACES_API_KEY`, the `GOOGLE_SPEECH_*` vars, `RERANK_ENABLED`, `SENTRY_DSN`, and `LANGSMITH_API_KEY`/`LANGSMITH_PROJECT` are read directly via `os.environ.get(...)` in their own modules (`services/warung_watch.py`, `app/services/speech.py`, `app/services/reranker.py`) rather than through `Settings`, so `core/config.py` alone won't show the full picture — this table plus a repo-wide `grep -rn "os.environ.get" apps/api` is the accurate way to find every one.

---

## CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | PR to `main`, push to `main`/`claude/**` | TypeScript typecheck, Next.js build, pytest, and an automated eval-quality gate (faithfulness + temporal-accuracy scoring) that blocks deploy on regression |
| `deploy.yml` | Push to `main` | Deploys `apps/web` to Netlify. `apps/api` deploys via Railway's own build hook. |
| `deadline-monitor.yml` | Daily 18:00 UTC (02:00 MYT), manual dispatch | Runs the Deadline Monitor agent directly on a GitHub runner |
| `ingest-sources.yml` | Weekly, Sunday 20:00 UTC, manual dispatch | Runs `scripts/ingest_feed.py` against every registered source in `scripts/sources.py` |
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

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, the exact commands CI runs, and PR conventions.

For exploratory product-direction notes (not a committed roadmap), see [`docs/ROADMAP.md`](docs/ROADMAP.md).

---

## License

Licensed under the [Apache License 2.0](LICENSE).

NakTahu AI is an independent project and is **not** an official Malaysian government service. Answers are generated from published government sources but are not legal, tax, immigration, or medical advice — always verify anything important with the relevant agency.
