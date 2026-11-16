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
| **Grant Finder** (backend: Eligibility Agent) | Multi-turn business grant-eligibility matching — conversational intake (business type, sector, revenue, headcount, Bumiputera status), hybrid retrieval against a seeded, source-cited grant database (Cradle Fund, MDEC, SME Corp, HRD Corp and others), scoring with near-miss detection, and a grant-stacking compatibility matrix (which programmes can legally be combined). Each top match is re-checked live against the agency's own page (Tavily, restricted to that agency's domain, deterministic date extraction, no LLM reads web text) and shown with a *last verified* stamp: `confirmed`, `changed`, `closed`, `no_signal` or `unavailable`, never silently passed. Optionally, a flag-gated Nemotron model split (Nebius Token Factory) handles intake extraction from free-text answers (fast model) and the streamed eligibility summary (reasoning model); the summary is served by the conversational SSE API (`/api/v1/eligibility`), while the web form flow shows the deterministic results only. Eligibility decisions themselves stay deterministic code. Statutory tax-incentive matching (Pioneer Status, ITA, RA) is a known, deliberately unbuilt gap — no verified source corpus for it exists yet, so it's not fabricated. |
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

## What's new (November 2026)

**Answer quality and trust**
- **Retrieval retry** (#285): a weak domain-filtered search is retried once with no domain filter and kept only if confidence improves. Switch it off with `RETRIEVAL_RETRY_ENABLED=false`.
- **Relevance gate** (#287): an official URL earns authority credit only if the chunk is on-topic (`ANALYST_RELEVANCE_FLOOR`, default 0.4). Off-topic chunks are never cited, and a query with nothing relevant goes to clarification.
- **Router retry** (#289): a classification ILMU returns in an unparseable form is retried once with a larger token budget and logged as `router_parse_failed`.
- **Answer-side support check**: an answer that says "I could not find it in the provided context" no longer goes out at the retrieval-based confidence (a live eval saw 0.81). `app/agents/answer_support.py` caps it at 0.35 and drops the source chips when the answer has no figures. It only ever lowers confidence.

**Corpus**
- **SSM company-incorporation sources** (#290): overview, step-by-step guide in English and Bahasa Malaysia, and the incorporation guidelines PDF.
- **One official source per tax topic**, replacing a single hand-written chunk that mixed reliefs, e-filing deadlines, RPGT and SST under a rate-table title: LHDN tax reliefs, withholding tax and RPGT rates; Customs MySST registration and business FAQ; the LHDN stamp duty First Schedule guideline (Bahasa Malaysia, with the tiered transfer rates); and the LHDN 2026 filing programme. The filing programme is a table PDF whose extracted text is scrambled but states the Form BE, Form B and company deadlines, and it must be replaced each year.
- **Source-specific extractors** `lhdn_content` (LHDN pages that are plain content, one chunk per table with its caption) and `eael_accordion` (Customs), and ingest dry-runs can print longer chunk previews (`preview_chars`).
- **Known gaps**: no official source found yet for the 7-year record-keeping rule, Form B for sole proprietors, or the non-resident individual rate.

**Measuring**
- **Live tax-accuracy eval** (`live-tax-eval.yml`): runs a 30-case answer key through the real pipeline with the embedding profile and chat model you choose, and prints each wrong answer with its scoring reason.
- **LLM latency benchmark** (`llm-latency-benchmark.yml`): time to first token and tokens per second, Nemotron on Nebius Token Factory against ILMU (needs the `NEMOTRON_*` settings).
- **Retrieval probe** (`retrieval-probe.yml`): for a question the eval gets wrong, the rank of the chunk holding the answer with no filter and under each domain filter, and `--find` to list which chunks mention a phrase and under which domain.
- **Faithfulness and context-precision live run** (#264, #265).

**Product**
- Landing page redesign with a trust strip and an accessibility statement, a skip link and a main landmark (#280 to #283); a prompt-first homepage, a guest chat shell with a free-limit state and a sourced-answer card with an Official/Community badge (#268 to #270).
- Warung Watch: responsive phone and desktop UI, accessibility fixes (#274, #277); health triage improvements (#271).
- Chat understands follow-up questions (#263); the grant finder stops re-asking what the intake form already collected (#261); a free-quota unit is refunded when a question is blocked or fails (#292).

**Platform**
- `/metrics` reports every uvicorn worker (#286); a Cloud Run deploy script for the API (#288).

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


### How a query moves through the core pipeline

The box art above shows the happy path only. The real graph (`apps/api/app/agents/graph.py`) has a few more
steps and branches, described here. State is one `AgentState` dict passed node to node.

| Node | What it does | When it fails or has nothing |
|---|---|---|
| `router_node` | Calls ILMU once to classify the query: **language** (BM or EN, which is also the language of the answer), **domain** (one of 13, e.g. `tax`, `business`, `property`) and a short **intent**. It also flags live-status and structured Parliament queries. If ILMU's reply does not parse as JSON it retries once with a larger token budget. | Two unparseable replies leave `domain=None`, so retrieval later searches every domain. |
| `guard_node` | Safety check. A harmful-intent keyword list is always on. An optional ILMU intent check (`GUARD_LLM_CHECK_ENABLED`, off by default) fails open. The domain label is never a reason to block. | A blocked query ends the graph after a refusal is streamed. |
| `rag_node` | Looks in Redis first, keyed by `sha256(query\|language\|domain)` with a one-hour TTL. On a miss it embeds the query with the active embedding profile and runs a hybrid search (0.7 cosine + 0.3 keyword) over `document_chunks`, filtered to the router's domain. It keeps the top 5 chunks (12 candidates first when `RERANK_ENABLED` is on). | If the domain-filtered search returns nothing it searches again with no filter. A search error returns no chunks. |
| `analyst_node` | The trust layer. Drops superseded and expired chunks, sets aside announced-but-not-yet-effective ones as *pending changes*, scores the rest, picks up to 3 citations and computes a confidence. | Confidence below **0.6** sets `needs_clarification`. |
| `retrieval_retry_node` | See below. | Skipped unless its conditions hold. |
| `synthesiser_node` | Streams the answer from ILMU, in the query's language. When it finishes it reads its own answer: if the opening sentence says the provided context has no answer, confidence is capped at 0.35 (below the 0.6 bar) and the answer is flagged for follow-up. This check can only lower confidence. | Falls back to Anthropic only when ILMU fails **before** its first token, so a partial answer is never followed by a second one. |
| `clarification` | Sends a fixed "please rephrase" prompt in the query's language. | |

**Branches the diagram leaves out**

- **Blocked** (`guard`): ends the graph.
- **Live status** (`"Is X packed right now?"`) goes to `warung_watch_node` and **structured Parliament lookups** (a bill's vote
  record, one MP) go to `parliament_query_node`. Both still pass `guard` first, then answer directly from live or relational
  data and skip retrieval, analysis and synthesis.
- **Low confidence** has two outcomes. If some usable material was retrieved, the synthesiser still answers, hedged, with a
  targeted follow-up question. Only when nothing was retrieved, or nothing retrieved is relevant, does the graph take the bare
  `clarification` node.
- **Retry** (`retrieval_retry_node`): when the analyst scores a **domain-filtered, freshly searched** query below 0.6, the graph
  runs **one** search with no domain filter, reusing the embedding, merges it with the first chunks and re-scores them through the
  same analyst. The new set is kept only if confidence strictly improves. This catches a misclassified domain, for example a
  question filed under `property` whose answer lives under `tax`. It never loops and never rewrites the query. It is skipped
  on a cache hit. Switch it off with `RETRIEVAL_RETRY_ENABLED=false`.

**How the analyst scores a chunk**

Relevance counts for up to half the score. A chunk gets credit for being an official source (+0.3) and for having a title
(+0.2) **only if its relevance reaches 0.4** (`ANALYST_RELEVANCE_FLOOR`). A government URL on an off-topic document is not
evidence, and such a chunk is never cited. Keyword overlap ignores common English and Bahasa Malaysia words and the word
"Malaysia". A stale chunk loses 0.15, so a fresher chunk on the same topic outranks it. An answer needs at least two chunks that
clear a minimum score. When confidence is low the reason is logged as one of `no_usable_chunks`, `weak_relevance`,
`too_few_supporting` or `no_relevant_evidence`.

**What the browser receives.** The answer streams over SSE (`token`, `citation`, `metadata`, `done`, `error`), at most 3 citation
chips per answer, each from real chunk metadata and never invented.

The vertical agents (grants, compliance, immigration and so on) run their own LangGraph graphs and share the router, retrieval and
tool layers, but not this graph.

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
| `NEMOTRON_FAST_MODEL` / `NEMOTRON_REASONING_MODEL` | Model IDs per role. Never defaulted: run `python scripts/nemotron_check.py` (from the repo root or `apps/api`) to list the live catalog and test-call your IDs |
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
