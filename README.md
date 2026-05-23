# Naktahu AI 🇲🇾

A bilingual (Bahasa Malaysia / English) civic AI assistant powered by RAG over DOSM (Department of Statistics Malaysia) open data.

## Architecture

```
naktahu-AI/
├── src/                        # Next.js 16 frontend (App Router)
│   ├── app/
│   │   ├── (landing)/page.tsx  # Landing page with TypewriterQuery
│   │   ├── chat/page.tsx       # Chat interface with SSE streaming
│   │   └── history/page.tsx    # Query history page
│   ├── components/
│   │   ├── chat/               # ChatBubble, ChatInput, CitationChip …
│   │   ├── landing/            # TypewriterQuery, LandingFeatures
│   │   ├── auth/AuthButton.tsx
│   │   ├── history/HistorySidebar.tsx
│   │   ├── language-toggle.tsx # BM/EN locale toggle
│   │   └── source-card.tsx     # DOSM source citation card
│   └── lib/
│       ├── hooks/              # useSSEStream, useVoiceInput
│       ├── supabase/           # client, server, middleware
│       └── i18n/               # I18nProvider
├── apps/api/                   # FastAPI backend
│   ├── main.py                 # App entry, CORS, lifespan
│   ├── routers/query.py        # SSE /api/v1/query (RAG-powered)
│   ├── routers/history.py      # GET/POST /api/v1/history
│   ├── routes/query.py         # REST /rag/query endpoint
│   ├── rag/
│   │   ├── embeddings.py       # OpenAI text-embedding-3-small
│   │   ├── retriever.py        # Supabase pgvector retriever
│   │   └── pipeline.py         # LCEL chain → gpt-4o-mini
│   ├── services/               # auth, history
│   ├── middleware/             # rate_limit, user_context
│   ├── data/dosm/              # Place DOSM CSVs here
│   ├── requirements.txt
│   └── .env.example
├── infra/supabase/
│   ├── migrations/
│   │   └── 001_enable_pgvector.sql
│   └── AUTH_SETUP.md
└── public/
    ├── locales/
    │   ├── en/common.json
    │   └── ms/common.json
    └── manifest.json
```

## Quick start

### 1. Frontend

```bash
pnpm install
pnpm dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local`.

### 2. Backend

```bash
cd apps/api
pip install -e ".[dev]"
cp .env.example .env   # fill in keys
uvicorn main:app --reload
```

### 3. Database

Apply the pgvector migration in your Supabase project:

```bash
supabase db push   # or paste infra/supabase/migrations/001_enable_pgvector.sql in the SQL editor
```

### 4. Add data

Place DOSM CSV files in `apps/api/data/dosm/` — see the README there for the expected format.

## Environment variables

| Variable | Service | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | API | OpenAI key for embeddings + GPT-4o-mini |
| `SUPABASE_URL` | API | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | API | Service role key |
| `JWT_SECRET` | API | Supabase JWT secret |
| `REDIS_URL` | API | Redis for session history |
| `NEXT_PUBLIC_API_URL` | Frontend | FastAPI base URL |
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend | Supabase anon key |

## Features

- **RAG pipeline** — DOSM CSV data → OpenAI embeddings → Supabase pgvector → GPT-4o-mini answer with citations
- **SSE streaming** — token-by-token response delivery
- **Bilingual** — Bahasa Malaysia / English, auto-detected
- **Auth** — Supabase SSR auth with session refresh
- **History** — Redis + Supabase session history
- **PWA** — service worker + manifest
- **Rate limiting** — SlowAPI per-IP and per-user limits
