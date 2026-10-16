# NakTahu AI

> **Ilmu tempatan, jawapan seketika.**
----

NakTahu AI is a Malaysian-focused, trilingual AI answer engine (Bahasa Malaysia, English, Mandarin) that delivers cited, government-sourced answers across 13 canonical domains — government, education, legal, finance, healthcare, EPF, tax, business, immigration, culture, parliament, property, and welfare. Beyond chat, it's an agentic platform: a set of vertical AI agents for grant matching, compliance drafting, retrenchment guidance, immigration, welfare eligibility, property, health triage, exam prep, investor due diligence, and parliamentary transparency; a crowdsourced live-status tool for local eateries (Warung Watch); and a metered Developer/Knowledge API for external integrators.

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
| **Grant Finder** (backend: Eligibility Agent) | Multi-turn business grant-eligibility matching — conversational intake (business type, sector, revenue, headcount, Bumiputera status), hybrid retrieval against a seeded, source-cited grant database (Cradle Fund, MDEC, SME Corp, HRD Corp and others), scoring with near-miss detection, and a grant-stacking compatibility matrix (which programmes can legally be combined). Each top match is re-checked live against the agency's own page (Tavily, restricted to that agency's domain, deterministic date extraction, no LLM reads web text) and shown with a *last verified* stamp: `confirmed`, `changed`, `closed`, `no_signal` or `unavailable`, never silently passed. Optionally, a flag-gated Nemotron model split (Nebius Token Factory) handles intake extraction (fast model) and the streamed eligibility summary (reasoning model); eligibility decisions themselves stay deterministic code. Statutory tax-incentive matching (Pioneer Status, ITA, RA) is a known, deliberately unbuilt gap — no verified source corpus for it exists yet, so it's not fabricated. |
| **Grant Draft Generator** | Given a selected grant and business profile, drafts an executive summary, use-of-funds narrative, a financial-projection *template* (explicitly never presented as real figures), and a required-document checklist; exports to PDF or Word. |
| **Compliance Drafter** | Multi-domain compliance report generation with a human-in-the-loop approval step before the final PDF is produced. |
| **SME Compliance Navigator (PatuhiKu)** | Cross-references a business profile against tax (LHDN), employment (EPF/SOCSO/EIS), and company (SSM) obligations in parallel. |
| **Immigration Navigator** | Conversational visa/permit intake grounded in immigration-domain retrieval. |
| **Retrenchment Navigator** | Guided retrenchment options — EIS unemployment-claim eligibility, statutory termination-benefit calculation (deterministic Employment Act arithmetic, never LLM-guessed), and a next-steps checklist. Free tier, 0 credits. |
| **Welfare Eligibility Agent** | Matches a household profile (income, state, dependents, OKU status, employment/housing) against cost-of-living and social-assistance schemes — deterministic, filter-first eligibility matching, same architecture as Grant Finder's scoring. Sourced from Ihsan MADANI's own listings via a dedicated scrape→verify→embed ingestion pipeline (`scripts/ingest_madani.py`, weekly), with an eligibility-rules review gate (`needs_review`) so an unverified scheme is never surfaced as "you qualify." Free tier, 0 credits. |
| **Property Concierge** | Guided property buyer/renter intake — lead-tier qualification, property-domain RAG citations (tenancy, strata, land title, NAPIC/OpenDOSM open sales data), and a shareable brief. Lets users paste in a listing URL themselves (with an OCR-from-photo option) rather than the agent sourcing live listings — see the agent's own module docstring for why it doesn't scrape licensed-valuer-gated listing sites. Free tier, 0 credits. |
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
- **Developer / Knowledge API** — a separate, API-key-authenticated surface (`/api/v1/public`, `/api/v1/developer`) for external integrators: single- and multi-domain query endpoints, streaming, a branded self-hosted Swagger UI at `/api/v1/public/docs`, key naming and one-click rotation (replace a leaked key's secret without losing its plan/limits/usage), and per-key usage tracking. Free tier available to any signed-in user, no Pro subscription required.
- **In-chat answer translation** — translate any answer between BM/EN/ZH on demand, independent of the query's own detected language, without re-running retrieval/synthesis.
- **Real social sharing** — WhatsApp/Telegram/Facebook share targets (each platform's own share composer, never automated posting) plus an optional AI-drafted caption, on top of the permalink system below.
- **Shareable answers** — generate a permalink for any answer.
- **Session history** — authenticated users get persistent query history (pro plan), plus a separate, non-plan-gated agent-run history (drafts, checklists, eligibility results) for any signed-in user.
- **Interactive citation cards** — hover or tap a citation chip for the full source title, a colour-coded confidence rating, staleness flag, and the direct source link, instead of only a truncated inline chip.
- **Document export** — Compliance Drafter, Grant Draft Generator, and Health Triage can each export their output to PDF (Grant Draft Generator also supports Word), rendered server-side (WeasyPrint / python-docx) and served via a signed, time-limited Supabase Storage URL.
- **Optional cross-encoder-style re-ranking** — a second retrieval pass over `hybrid_search`'s candidate pool, re-scoring (query, chunk) pairs together via the same ILMU chat client rather than a new provider. Off by default (`RERANK_ENABLED`) pending an eval-set comparison; degrades to the unranked order on any failure.
- **Embedding profiles** — search can run on either the OpenAI corpus model (`openai`, 1536-dim) or ILMU's native `bge-m3` (`ilmu_bge_m3`, 1024-dim), each with its own column and search RPC. `EMBEDDING_PROFILE` picks what search reads; `EMBEDDING_WRITE_PROFILES` picks what ingestion fills. A query vector is never compared against another model's column. `scripts/reembed_corpus.py` backfills a new profile (resumable) and compares retrieval before cutover.
- **Redis-backed caching** — repeated queries skip retrieval entirely (content-hash keyed, TTL-bound).
- **Tiered rate limiting** — anonymous and authenticated users get different request budgets; the Developer API is independently metered per key.
- **Plan-based access** — free / student / pro / business tiers, plus an independent "investor" entitlement for the Investor Intelligence product — read from the user's Supabase session, not a separate subscriptions table.

### Quality and evaluation
- **Deploy eval gate** (`scripts/evals/run_eval_gate.py`) — blocks deploy on a temporal-accuracy regression (chunk currency). Its faithfulness gate (0.75) is enforced only when a score is supplied; otherwise it prints `NOT MEASURED` rather than passing silently.
- **Grant Agent decision evals** (`apps/api/evals/test_grant_agent.py`) — credential-free: match precision 1.00, stacking accuracy 1.00, and "never confirm a deadline the evidence does not support".
- **Trilingual intake eval** (`apps/api/evals/test_grant_intake_multilingual.py`) — the same six business descriptions in BM, EN and ZH. Parity checks run in CI; the live accuracy test (`RUN_LIVE_EVALS=1`) requires every language at or above 0.85 and Mandarin within 0.10 of English. It has not been run against a live model yet.
- **Faithfulness judge pilot** (`scripts/evals/faithfulness/`) — scaffolding for the missing faithfulness measurement, with a Nebius job runner. Not yet calibrated: it needs about 90 human-labelled examples.

---

## What's new (October 2026)
- **Budget 2027 from official MOF sources** — documents are fetched only from `*.mof.gov.my` (every redirect hop is checked) and identity-checked against the PDF's own text before anything is stored.
- **ILMU-native embeddings** — side-by-side `bge-m3` column, v2 search RPCs, and a resumable re-embed of the whole corpus (migration 056).
- **Source-specific extractors** — LHDN rate tables are ingested with their numbers intact (`scripts/html_extractors.py`), with a page inspector workflow (`inspect-page.yml`) for writing more.
- **Self-diagnosing weekly ingest** — fetches retry transient failures, each run ends with a per-source recap, and sources marked `known_broken` (with a reason) are skipped instead of turning the job red.
- **Live grant verification** — Tavily-backed deadline checks with last-verified stamps, plus a nightly refresh job (`grant-refresh.yml`).
- **Nemotron model split** for the Grant Agent only, behind `ELIGIBILITY_USE_NEMOTRON`; ILMU stays the primary provider everywhere else.
- **Mandarin coverage measured** for the Grant Agent's intake.

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
│       └── scripts/            — 3 distinct ingestion pipelines: ingest.py
│                                  (→ dosm_documents, CSV), ingest_feed.py
│                                  (→ document_chunks, what RAG retrieval
│                                  actually reads — RSS/HTML + Hansard),
│                                  ingest_madani.py (→ madani_scheme, welfare
│                                  eligibility data)
├── packages/
│   └── shared-types/           — TypeScript types shared across the web workspace
├── infra/
│   ├── supabase/migrations/    — versioned SQL schema (45+ files)
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
| `ILMU_EMBEDDING_MODEL` | ILMU gateway route to the OpenAI corpus model; empty disables that route |
| `EMBEDDING_PROFILE` | `openai` (default) or `ilmu_bge_m3` — which model/column/RPC serves search |
| `EMBEDDING_WRITE_PROFILES` | Comma-separated profiles ingestion fills (default `openai`) |
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
| `ELIGIBILITY_USE_NEMOTRON` | Enables the Grant Agent's Nemotron model split (default `false`). Also needs `NEMOTRON_API_KEY` and the role's model ID |
| `NEMOTRON_API_KEY` / `NEMOTRON_BASE_URL` | Nebius Token Factory key and OpenAI-compatible endpoint |
| `NEMOTRON_FAST_MODEL` / `NEMOTRON_REASONING_MODEL` | Model IDs per role. Never defaulted: run `python scripts/nemotron_check.py` to list the live catalog and test-call your IDs |
| `TAVILY_API_KEY` | Live grant-deadline verification and the nightly refresh. Unset means grants show as unverified |
| `RERANK_ENABLED` | Turns on the optional cross-encoder-style re-ranking pass over hybrid-search results (default `false`) |

Most are validated via `apps/api/core/config.py`'s `Settings` object — but not all: `GOOGLE_PLACES_API_KEY`, the `GOOGLE_SPEECH_*` vars, `RERANK_ENABLED`, `SENTRY_DSN`, and `LANGSMITH_API_KEY`/`LANGSMITH_PROJECT` are read directly via `os.environ.get(...)` in their own modules (`services/warung_watch.py`, `app/services/speech.py`, `app/services/reranker.py`) rather than through `Settings`, so `core/config.py` alone won't show the full picture — this table plus a repo-wide `grep -rn "os.environ.get" apps/api` is the accurate way to find every one.

---

## CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | PR to `main`, push to `main`/`claude/**` | TypeScript typecheck, Next.js build, pytest, and an automated eval-quality gate (faithfulness + temporal-accuracy scoring) that blocks deploy on regression |
| `deploy.yml` | Push to `main` | Deploys `apps/web` to Netlify. `apps/api` deploys via Railway's own build hook. |
| `deadline-monitor.yml` | Daily 18:00 UTC (02:00 MYT), manual dispatch | Runs the Deadline Monitor agent directly on a GitHub runner |
| `ingest-sources.yml` | Weekly, Sunday 20:00 UTC, manual dispatch | Runs `scripts/ingest_feed.py` against every registered source in `scripts/sources.py` except those marked `known_broken`. Dry-run unless dispatched with `write_mode=live`; ends with a per-source recap table |
| `ingest-budget-2027.yml` | Daily 12:00 UTC on 9–16 October, manual dispatch | Ingests the Budget 2027 documents from official MOF URLs once published (dry-run unless `write_mode=live`) |
| `reembed-corpus.yml` | Manual dispatch | Probe, backfill or compare an embedding profile (`probe` / `backfill` / `compare`) |
| `grant-refresh.yml` | Daily 17:30 UTC, manual dispatch | Re-verifies every active grant against its agency's site (Tavily); dry-run unless the repo variable `GRANT_REFRESH_LIVE` is `true` |
| `inspect-page.yml` | Manual dispatch, or a push to `claude/**` that edits `.github/inspect-targets.txt` | Prints a page's structure from a GitHub runner, for writing source-specific extractors |
| `ingest-madani.yml` | Weekly, Sunday 21:00 UTC, manual dispatch | Runs `scripts/ingest_madani.py` — scrapes Ihsan MADANI's welfare-scheme listings into `madani_scheme` (defaults to `--dry-run`; selectors need live-site verification before a real run is trusted — see the script's own docstring) |
| `lighthouse.yml` | Push to `main`, manual dispatch | Lighthouse CI audit, gated on a minimum PWA score |
| `ping-supabase.yml` | Mon + Thu 9am UTC | Keeps the Supabase free-tier project from auto-pausing |

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router), React 19, TypeScript (strict), Tailwind CSS 4, Framer Motion, Web Speech API |
| Backend | Python 3.11+, FastAPI, LangGraph, LangChain Core |
| LLM | ILMU API (primary) + Anthropic Claude (synthesis fallback only). Grant Agent only: optional Nemotron on Nebius Token Factory |
| Embeddings | Selectable profile: OpenAI `text-embedding-3-small` (default) or ILMU `bge-m3`, each with its own column and search RPC |
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
