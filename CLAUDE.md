# NakTahu AI

**Tagline:** Ilmu tempatan, jawapan seketika.
**Purpose:** Malaysian-focused bilingual AI answer engine (Bahasa Malaysia + English)
**Repo root:** `naktahu-ai/`

## Monorepo layout

```
apps/web          — Next.js 15 frontend
apps/api          — FastAPI backend
packages/shared-types
scripts/ingest
infra/
```

## Stack — never deviate without explicit instruction

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 App Router, TypeScript strict, Tailwind CSS, shadcn/ui, Framer Motion |
| Backend | Python 3.11+, FastAPI, LangGraph 0.2+, LangChain Core |
| LLM | ILMU API (primary, OpenAI-compatible) + `claude-sonnet-4-20250514` (synthesis fallback) |
| Embeddings | ILMU API (`ilmu-embedding` model, OpenAI-compatible SDK) |
| Vector DB | Supabase with pgvector extension |
| Cache | Redis (Render) via redis-py asyncio |
| Auth | Supabase Auth — email + Google OAuth, JWT validated in FastAPI middleware |
| Deploy | Vercel (web), Render (api + redis), Supabase cloud |
| CI/CD | GitHub Actions — lint + typecheck + pytest on PR, deploy on main merge |

## Environment variables

All secrets live in `.env.local` (web) and `.env` (api). Never hardcode. Never commit. Reference by name only in code.

**Web (`.env.local`):**
```
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

**API (`.env`):**
```
ANTHROPIC_API_KEY=
ILMU_API_KEY=
ILMU_BASE_URL=
ILMU_CHAT_MODEL=
ILMU_EMBEDDING_MODEL=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
REDIS_URL=
JWT_SECRET=
SENTRY_DSN=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=naktahu-ai
```

## Naming conventions

- **Python files:** snake_case (e.g. `router_node.py`, `vector_store.py`)
- **TypeScript files:** kebab-case (e.g. `citation-chip.tsx`, `use-sse-stream.ts`)
- **Python:** snake_case functions and variables, PascalCase classes
- **TypeScript:** camelCase variables/functions, PascalCase components and types
- **Database tables:** snake_case (e.g. `document_chunks`, `user_sessions`)
- **Redis keys:** colon-separated namespaces (e.g. `session:{user_id}:history`, `cache:{sha256_hash}`)
- **API routes:** `/api/v1/` prefix on all FastAPI routes

## Code quality rules

- TypeScript strict mode — no `any`, no implicit returns
- Python type hints on all function signatures — mypy compatible
- No `print()` in production Python — use `structlog`
- No `console.log` in production TypeScript — remove before commit
- Every FastAPI endpoint has a Pydantic request and response model
- Every React component has explicit TypeScript prop types — no implicit props
- Tailwind only — no inline styles, no CSS modules, no styled-components
- shadcn/ui components only for UI primitives — never raw HTML form elements in React

## LangGraph agent architecture

The pipeline is a `StateGraph` with 4 nodes and conditional edges. Execution order:

1. **`router_node`** — classifies intent, domain (`government`/`education`/`legal`/`finance`/`health`/`culture`), and language (`bm`/`en`). Uses ILMU chat model with structured JSON output.
2. **`rag_node`** — hybrid search on Supabase pgvector (cosine 0.7 + BM25 0.3). Returns top 5 chunks with source metadata. Checks Redis cache first with `sha256(query+language+domain)` key.
3. **`analyst_node`** — scores citation relevance (0.0–1.0), maps `source_url` from chunk metadata, sets `confidence_score` on state. If confidence < 0.4, sets `needs_clarification` flag.
4. **`synthesiser_node`** — calls ILMU primary (Anthropic fallback) with streaming. System prompt enforces bilingual output matching query language. Streams tokens via `AsyncGenerator` back to SSE endpoint.

**State `TypedDict` fields:**
`query`, `language`, `domain`, `session_id`, `user_id`, `retrieved_chunks`, `citations`, `confidence_score`, `needs_clarification`, `streaming_token_buffer`, `error`

## SSE streaming contract

The `/api/v1/query` endpoint returns `text/event-stream`. Event types:

```
event: token     data: {"text": "..."}
event: citation  data: {"title": "...", "url": "...", "ministry": "..."}
event: metadata  data: {"confidence": 0.87, "domain": "government", "language": "bm"}
event: done      data: {}
event: error     data: {"message": "..."}
```

The Next.js frontend consumes this via a custom `useSSEStream` hook. Never buffer the full response — render tokens as they arrive.

## Bilingual rules

- Detect query language at `router_node`. Store as `"bm"` or `"en"` on state.
- Synthesiser system prompt: *"Respond in the same language as the query. If the query is in Bahasa Malaysia, respond in Bahasa Malaysia. If in English, respond in English. If code-switched, match the dominant language."*
- i18n UI strings live in `apps/web/lib/i18n/bm.json` and `en.json`. Never hardcode UI strings.
- The language toggle in the navbar switches UI strings only — it does not override query language detection.

## Citation chip format

Every answer must surface 1–3 citation chips. Each chip renders:

```ts
{ title: string, ministry: string, url: string, confidence: number }
```

Source URLs must be real `gov.my` or related official Malaysian government domains. Never fabricate URLs. If no real URL exists in the chunk metadata, omit the citation rather than hallucinate.

## Redis caching rules

- **Cache key:** `sha256(query.lower().strip() + "|" + language + "|" + domain)`
- **TTL:** 3600 seconds (1 hour) for query results
- **TTL:** 2592000 seconds (30 days) for user session history
- Session history stored as Redis List: `LPUSH session:{user_id}:history`, `LTRIM` to 50 entries
- Cache hit skips `rag_node` and `analyst_node` — jumps directly to `synthesiser_node` with cached chunks

## Auth rules

- Supabase JWT is validated in FastAPI via a dependency: `get_current_user()`
- Unauthenticated users get an anonymous session token (UUID, stored in `localStorage`) with rate limit 30 req/hour
- Authenticated users get rate limit 200 req/hour
- History endpoint requires authentication — return 401 for anonymous requests

## Rate limiting

- Use `slowapi` with Redis backend
- Anonymous: 30/hour keyed on IP
- Authenticated: 200/hour keyed on `user_id`
- Return 429 with `Retry-After` header

## Testing standards

- **Python:** pytest + pytest-asyncio. Every agent node has a unit test with mocked Supabase and Redis.
- **TypeScript:** Vitest for hooks and utilities. No component testing required in v1.
- GitHub Actions runs `pytest` and `tsc --noEmit` on every PR.

## Do not do these things

- Do not change provider order without an explicit architecture decision: ILMU is primary for router/rag/synthesis, and `claude-sonnet-4-20250514` is fallback for synthesis only.
- Never expose `SUPABASE_SERVICE_ROLE_KEY` to the frontend under any circumstances.
- Never use `fetch()` in agent nodes — use the official Anthropic Python SDK and `supabase-py`.
- Never store raw query text in Redis keys — always hash first.
- Never skip the `analyst_node` confidence check — it is the trust layer.
- Never render a citation chip with a fabricated URL.
