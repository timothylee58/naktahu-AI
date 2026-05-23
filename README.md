# Naktahu AI 🇲🇾

> **NakTahu** — *"Nak Tahu"* means "Want to Know" in Bahasa Malaysia.

A bilingual (Bahasa Malaysia / English) civic AI assistant that answers questions about Malaysian statistics and government data, grounded in [DOSM](https://www.dosm.gov.my) (Department of Statistics Malaysia) open data via a RAG pipeline.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
  - [1. Clone and install](#1-clone-and-install)
  - [2. Configure environment](#2-configure-environment)
  - [3. Set up Supabase](#3-set-up-supabase)
  - [4. Start the API](#4-start-the-api)
  - [5. Start the frontend](#5-start-the-frontend)
  - [6. Ingest DOSM data](#6-ingest-dosm-data)
- [Environment variables](#environment-variables)
- [RAG pipeline](#rag-pipeline)
- [Data ingestion](#data-ingestion)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Development](#development)

---

## Features

| Feature | Detail |
|---------|--------|
| **RAG pipeline** | DOSM CSV data → `text-embedding-3-small` → Supabase pgvector → `gpt-4o-mini` answer with citations |
| **SSE streaming** | Token-by-token response delivery, no polling |
| **Bilingual** | Bahasa Malaysia / English — language auto-detected; system prompt instructs the model to reply in kind |
| **Source citations** | Every answer links back to the source dataset, year, and ministry |
| **Auth** | Supabase SSR auth (Google OAuth + email) with session refresh middleware |
| **Query history** | Per-user history stored in Redis (fast read) and Supabase `user_sessions` (durable) |
| **PWA** | Service worker + web app manifest for installable mobile experience |
| **Rate limiting** | SlowAPI per-IP and per-user limits on the query endpoint |
| **Voice input** | Browser speech recognition via `useVoiceInput` hook |

---

## Architecture

```
Browser
  │
  ├── Next.js 16 (App Router)          src/
  │     ├── Landing page               app/(landing)/page.tsx
  │     ├── Chat UI                    app/chat/page.tsx
  │     └── History page               app/history/page.tsx
  │
  └── FastAPI                          apps/api/
        ├── POST /api/v1/query  ──SSE──► RAG pipeline
        │     ├── Retrieve               pgvector similarity search
        │     ├── Generate               gpt-4o-mini via LangChain LCEL
        │     └── Cite                   source metadata from DOSM CSVs
        ├── GET  /api/v1/history
        ├── POST /api/v1/history
        └── POST /rag/query     ──JSON─► same pipeline, REST response

Supabase (PostgreSQL + pgvector)
  ├── dosm_documents   — embedded DOSM chunks
  └── user_sessions    — durable query history

Redis
  └── session_history:{user_id}   — fast history reads
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | ≥ 20 | Next.js frontend |
| pnpm | ≥ 9 | Frontend package manager |
| Python | ≥ 3.11 | FastAPI backend |
| Redis | any | Session history cache |
| Supabase project | — | pgvector + auth + history table |
| OpenAI API key | — | Embeddings + completions |

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/timothylee58/naktahu-AI.git
cd naktahu-AI

# Frontend dependencies
pnpm install

# Backend dependencies
cd apps/api
pip install -e ".[dev]"
cd ../..
```

### 2. Configure environment

**Frontend** — copy and fill in `.env.local`:

```bash
cp .env.local.example .env.local
```

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-public-key
NEXT_PUBLIC_API_URL=http://localhost:8000
API_BACKEND_URL=http://localhost:8000
```

**Backend** — copy and fill in `apps/api/.env`:

```bash
cp apps/api/.env.example apps/api/.env
```

```env
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
JWT_SECRET=your-supabase-jwt-secret
REDIS_URL=redis://localhost:6379/0
```

### 3. Set up Supabase

Run both SQL scripts in your Supabase **SQL editor** (or via `supabase db push`):

**pgvector + DOSM documents table:**

```sql
-- infra/supabase/migrations/001_enable_pgvector.sql
create extension if not exists vector;

create table if not exists dosm_documents (
  id bigserial primary key,
  content text not null,
  metadata jsonb,
  embedding vector(1536)
);

create or replace function match_documents (
  query_embedding vector(1536),
  match_count int default 5
) returns table (id bigint, content text, metadata jsonb, similarity float)
language sql stable as $$
  select id, content, metadata,
         1 - (embedding <=> query_embedding) as similarity
  from dosm_documents
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

**User sessions table** (for query history):

```sql
create table if not exists public.user_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  query text not null,
  language text not null default 'en',
  domain text not null default 'general',
  response_summary text not null,
  citations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.user_sessions enable row level security;
```

For Google OAuth and JWT setup see [`infra/supabase/AUTH_SETUP.md`](infra/supabase/AUTH_SETUP.md).

### 4. Start the API

```bash
cd apps/api
uvicorn main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

> Without `OPENAI_API_KEY` the `/api/v1/query` endpoint returns a stub response — useful for frontend development without incurring API costs.

### 5. Start the frontend

```bash
pnpm dev
# http://localhost:3000
```

### 6. Ingest DOSM data

Place DOSM CSV files in `apps/api/data/dosm/` then run:

```bash
cd apps/api

# Dry-run first to verify format and estimate cost
python -m scripts.ingest --dir data/dosm/ --dry-run

# Ingest for real
python -m scripts.ingest --dir data/dosm/
```

See [Data ingestion](#data-ingestion) for CSV format details.

---

## Environment variables

### Backend (`apps/api/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes* | — | OpenAI key for embeddings + GPT-4o-mini. Without it, the API returns stub responses. |
| `SUPABASE_URL` | Yes | `http://localhost:54321` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | — | Service role key (server-side only, never exposed to browser) |
| `JWT_SECRET` | Yes | dev default | Supabase JWT secret (Project Settings → API → JWT Secret) |
| `SUPABASE_JWT_AUD` | No | `authenticated` | JWT audience claim |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection string |

### Frontend (`.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase public anon key |
| `NEXT_PUBLIC_API_URL` | No | FastAPI base URL (defaults to same origin in production) |
| `API_BACKEND_URL` | No | Server-side rewrite target (defaults to `http://localhost:8000`) |

---

## RAG pipeline

```
User question
     │
     ▼
OpenAI text-embedding-3-small
     │  (1536-dimensional vector)
     ▼
Supabase pgvector — match_documents()
     │  (top-5 nearest chunks by cosine similarity)
     ▼
LangChain LCEL chain
     │  context = joined chunk texts
     │  prompt  = bilingual system prompt + user question
     ▼
gpt-4o-mini
     │
     ▼
Answer + source citations streamed via SSE
```

**System prompt** instructs the model to:
- Always cite the source dataset and year
- Respond in the same language the user used (BM or EN)
- Say so honestly if relevant data cannot be found

**Confidence score** is derived from the number of relevant documents retrieved (0–1 scale). A warning badge appears in the chat UI when confidence < 0.4.

---

## Data ingestion

### CSV format

Place files in `apps/api/data/dosm/`. Required column: `content`. All others are optional metadata.

| Column | Description | Example |
|--------|-------------|---------|
| `content` | Text chunk to embed and retrieve | `"Malaysia's population reached 32.7 million in 2022."` |
| `dataset` | Dataset name | `"Population Estimates 2022"` |
| `year` | Publication year | `2022` |
| `ministry` | Producing ministry | `"DOSM"` |
| `url` | Source URL | `"https://www.dosm.gov.my/v2/"` |
| `source_title` | Human-readable title | `"Demographic Statistics 2022"` |

### Ingestion commands

```bash
cd apps/api

# All CSVs in data/dosm/
python -m scripts.ingest --dir data/dosm/

# Single file
python -m scripts.ingest --file data/dosm/population.csv

# Dry-run — embeds but skips Supabase write
python -m scripts.ingest --dir data/dosm/ --dry-run

# Custom batch size (default: 100 rows per OpenAI request)
python -m scripts.ingest --dir data/dosm/ --batch-size 50
```

### Recommended data sources

- [data.gov.my](https://data.gov.my) — Malaysia's official open data portal
- [DOSM OpenDOSM](https://open.dosm.gov.my) — Statistics open data hub
- [DOSM Publications](https://www.dosm.gov.my) — Census, labour force, GDP reports

---

## API reference

### `POST /api/v1/query` — SSE stream

Streams the RAG answer token-by-token.

**Request body:**
```json
{
  "query": "What is Malaysia's population in 2022?",
  "language": "en",
  "domain": "general",
  "session_id": "optional-uuid"
}
```

**SSE events:**

| Event | Payload | Description |
|-------|---------|-------------|
| `token` | `{"text": "..."}` | Streamed answer chunk |
| `citation` | `{source_title, source_url, ministry}` | Source reference |
| `done` | `{"ok": true, "citations": [...], "metadata": {...}}` | Stream complete |
| `error` | `{"message": "..."}` | Pipeline error |

### `POST /rag/query` — REST JSON

Non-streaming RAG query for server-side or batch use.

**Request body:**
```json
{
  "question": "What is Malaysia's GDP growth rate?",
  "language": "en",
  "session_id": null
}
```

**Response:**
```json
{
  "answer": "Malaysia's GDP grew by 8.7% in 2022...",
  "sources": [
    {
      "dataset": "National Accounts 2022",
      "year": "2022",
      "url": "https://www.dosm.gov.my/...",
      "ministry": "DOSM"
    }
  ],
  "confidence": 0.8
}
```

### `GET /api/v1/history` — Query history

Returns the authenticated user's recent queries. Requires `Authorization: Bearer <token>`.

### `GET /health`

```json
{"status": "ok"}
```

---

## Project structure

```
naktahu-AI/
├── src/                              # Next.js 16 frontend
│   ├── app/
│   │   ├── (landing)/page.tsx        # Landing page + TypewriterQuery animation
│   │   ├── chat/page.tsx             # Chat interface (SSE streaming)
│   │   ├── history/page.tsx          # Query history view
│   │   └── layout.tsx                # Root layout + I18nProvider
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatBubble.tsx        # Message bubble (user + assistant)
│   │   │   ├── ChatInput.tsx         # Input bar + mic button
│   │   │   ├── CitationChip.tsx      # Source link chip
│   │   │   ├── StreamingText.tsx     # Animated token stream
│   │   │   └── ThinkingIndicator.tsx # Loading animation
│   │   ├── landing/
│   │   │   ├── TypewriterQuery.tsx   # Animated example queries
│   │   │   └── LandingFeatures.tsx   # Feature cards
│   │   ├── history/HistorySidebar.tsx
│   │   ├── auth/AuthButton.tsx
│   │   ├── language-toggle.tsx       # BM ↔ EN switcher
│   │   └── source-card.tsx           # DOSM citation card
│   └── lib/
│       ├── hooks/
│       │   ├── useSSEStream.ts       # SSE client hook
│       │   └── useVoiceInput.ts      # Speech recognition hook
│       ├── supabase/
│       │   ├── client.ts             # Browser Supabase client
│       │   ├── server.ts             # Server Supabase client
│       │   └── middleware.ts         # Session refresh middleware
│       ├── i18n/index.tsx            # I18nProvider + useI18n hook
│       └── types.ts                  # Shared TypeScript types
│
├── apps/api/                         # FastAPI backend
│   ├── main.py                       # App factory, CORS, lifespan startup
│   ├── core/config.py                # Pydantic settings (env vars)
│   ├── routers/
│   │   ├── query.py                  # POST /api/v1/query (SSE, RAG-powered)
│   │   └── history.py                # GET/POST /api/v1/history
│   ├── routes/
│   │   └── query.py                  # POST /rag/query (REST JSON)
│   ├── rag/
│   │   ├── embeddings.py             # OpenAI text-embedding-3-small
│   │   ├── retriever.py              # Supabase pgvector retriever
│   │   └── pipeline.py               # LCEL chain → gpt-4o-mini
│   ├── scripts/
│   │   └── ingest.py                 # CSV → embed → upsert to dosm_documents
│   ├── services/
│   │   ├── auth.py                   # JWT validation, UserContext
│   │   └── history.py                # Redis + Supabase history persistence
│   ├── middleware/
│   │   ├── rate_limit.py             # SlowAPI limits
│   │   └── user_context.py           # Attach user to request state
│   ├── data/dosm/                    # Place DOSM CSVs here
│   ├── tests/                        # pytest test suite
│   ├── requirements.txt
│   └── pyproject.toml
│
├── infra/supabase/
│   ├── migrations/
│   │   └── 001_enable_pgvector.sql   # vector ext, dosm_documents, match_documents
│   └── AUTH_SETUP.md                 # Google OAuth + JWT configuration guide
│
└── public/
    ├── locales/
    │   ├── en/common.json            # English UI strings
    │   └── ms/common.json            # Bahasa Malaysia UI strings
    ├── manifest.json                 # PWA manifest
    └── sw.js                         # Service worker
```

---

## Development

### Run tests

```bash
cd apps/api
python -m pytest tests/
```

### Type check frontend

```bash
pnpm build   # includes tsc type check
```

### Lint

```bash
pnpm lint
```

### Add new DOSM datasets

1. Download a CSV from [data.gov.my](https://data.gov.my) or [open.dosm.gov.my](https://open.dosm.gov.my)
2. Ensure it has a `content` column (one row per text chunk)
3. Add optional metadata columns: `dataset`, `year`, `ministry`, `url`
4. Run `python -m scripts.ingest --file data/dosm/your-file.csv`

### Extend the RAG pipeline

The pipeline lives in `apps/api/rag/pipeline.py`. To change the model, system prompt, or retrieval strategy, edit that file — it exports a single `run_query(question, language)` async function that the SSE and REST routes both call.
