# Naktahu API

FastAPI service powering the NakTahu AI answer engine. Python 3.11+.

---

## Overview

The API receives natural-language queries (Bahasa Malaysia or English), routes them through a four-node LangGraph agent pipeline, and streams the response back to the client over Server-Sent Events (SSE). Authentication is handled via Supabase JWT. Rate limiting is enforced via slowapi backed by Redis.

---

## Endpoints

### `POST /api/v1/query`

Accepts a query and streams the answer as SSE.

**Auth:** Optional. Anonymous requests are permitted but rate-limited more aggressively.

**Request body:**
```json
{
  "query": "Apakah syarat untuk memohon MyKad?",
  "session_id": "uuid-string"
}
```

**Response:** `Content-Type: text/event-stream` — see [SSE Contract](#sse-contract).

**Rate limits:**
- Anonymous (keyed on IP): 30 requests/hour
- Authenticated (keyed on `user_id`): 200 requests/hour
- Exceeded requests receive HTTP 429 with a `Retry-After` header.

---

### `GET /api/v1/history`

Returns the session query history for the authenticated user.

**Auth:** Required. Returns HTTP 401 for anonymous requests.

---

## Agent Pipeline

The pipeline is a LangGraph `StateGraph` with four nodes executed in sequence. State is carried in `AgentState` (defined in `app/models/state.py`).

**State fields:** `query`, `language`, `domain`, `session_id`, `user_id`, `retrieved_chunks`, `citations`, `confidence_score`, `needs_clarification`, `streaming_token_buffer`, `error`

### 1. `router_node` — `app/agents/router_node.py`

Classifies the query into:
- **language:** `bm` (Bahasa Malaysia), `en` (English), or `zh` (Chinese/Mandarin)
- **domain:** `government`, `education`, `legal`, `finance`, `healthcare`, `epf`, `tax`, `business`, `immigration`, or `culture`

Uses the ILMU chat model with structured JSON output. A deterministic CJK Unicode range check runs after the LLM call and overrides the language result when Chinese characters are detected, preventing misclassification of Chinese queries as BM.

### 2. `rag_node` — `app/agents/rag_node.py`

Performs hybrid search on Supabase pgvector:
- Cosine similarity weight: 0.7
- BM25 weight: 0.3
- Returns top 5 chunks with source metadata.

Before querying Supabase, checks Redis for a cached result using the key `cache:{sha256(query|language|domain)}`. On a cache hit, skips retrieval and passes cached chunks directly to the analyst. On embedding errors, fails gracefully and continues with an empty chunk list.

### 3. `analyst_node` — `app/agents/analyst_node.py`

Scores the relevance of each retrieved chunk (0.0–1.0) and sets `confidence_score` on state. Maps `source_url` from chunk metadata to build citation objects. If `confidence_score < 0.6`, sets `needs_clarification = True`.

### 4. `synthesiser_node` — `app/agents/synthesiser_node.py`

Streams the final answer via `AsyncGenerator`:
- **Primary LLM:** ILMU API (OpenAI-compatible)
- **Fallback LLM:** Anthropic `claude-sonnet-4-20250514`

A language-specific instruction is prepended to the system prompt to enforce response language matching the query language. If both LLMs fail, a localized degraded message is returned instead of a hard error.

---

## SSE Contract

Every token, citation, and metadata item is sent as a discrete SSE event. Never buffer the full response.

```
event: token     data: {"text": "..."}
event: citation  data: {"title": "...", "url": "...", "ministry": "..."}
event: metadata  data: {"confidence": 0.87, "domain": "government", "language": "bm"}
event: done      data: {}
event: error     data: {"message": "..."}
```

- `token` events arrive incrementally as the LLM streams.
- `citation` events carry real `gov.my` or official Malaysian government URLs sourced from chunk metadata. Fabricated URLs are never emitted.
- `metadata` is sent once, after synthesis begins.
- `done` signals stream completion. The client should close the connection.
- `error` is sent in place of `done` if an unrecoverable error occurs.

---

## Redis Caching

| Purpose | Key pattern | TTL |
|---|---|---|
| Query result cache | `cache:{sha256(query\|language\|domain)}` | 3600 s (1 hour) |
| User session history | `session:{user_id}:history` | 2592000 s (30 days) |

Session history is stored as a Redis List (`LPUSH` + `LTRIM` to 50 entries). A cache hit on a query result bypasses the vector database search.

---

## Running Locally

```bash
uvicorn app.main:app --reload
```

The module path is `app.main:app`. Ensure a `.env` file is present in `apps/api/` with all required variables before starting.

**Required environment variables:**

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

---

## Running Tests

```bash
pytest tests/ -v
```

Each agent node has a unit test with mocked Supabase and Redis dependencies. GitHub Actions runs the full test suite plus `tsc --noEmit` on every pull request.

---

## Key Files

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI app entry point, route registration, middleware |
| `app/agents/router_node.py` | Intent, language, and domain classifier |
| `app/agents/rag_node.py` | Hybrid vector search + Redis cache layer |
| `app/agents/analyst_node.py` | Citation relevance scoring and confidence check |
| `app/agents/synthesiser_node.py` | Streaming LLM synthesis with ILMU/Anthropic fallback |
| `app/models/state.py` | `AgentState` TypedDict definition |
| `app/services/llm_client.py` | ILMU and Anthropic client setup |
| `app/services/vector_store.py` | Supabase pgvector query helpers |
