# NakTahu Knowledge API (Part 3)

Developer API with API-key auth, metering, public JSON/SSE endpoints, and embeddable widget.

## Apply migration

Run `infra/supabase/migrations/014_api_keys.sql` on your Supabase project.

## API tiers

| Plan | Price | Calls/mo | Rate limit | Features |
|------|-------|----------|------------|----------|
| starter | RM 49 | 5,500 | 10/min | JSON + citations |
| growth | RM 149 | 50,000 | 60/min | SSE stream, multi-domain |
| widget | RM 99 | 5,500 | 10/min | Domain-locked embed |
| white_label | RM 299 | 50,000 | 30/min | Widget without branding |
| enterprise | custom | unlimited | 1000/min | All features |

## Endpoints

- `POST /api/v1/public/query` — JSON answer + citations (`X-NakTahu-Key` header)
- `POST /api/v1/public/query/stream` — SSE (Growth+)
- `POST /api/v1/public/query/multi` — parallel multi-domain (Growth+)
- `GET /api/v1/public/domains` — domain chunk counts
- `GET /api/v1/public/openapi.json` — OpenAPI spec
- `GET /api/v1/public/docs` — Swagger UI

Developer dashboard (JWT auth):

- `POST /api/v1/developer/keys` — generate key (max 3 per user)
- `GET /api/v1/developer/keys` — list prefixes
- `DELETE /api/v1/developer/keys/{id}` — revoke
- `GET /api/v1/developer/usage` — usage stats

## Widget embed

```html
<script src="https://naktahu.netlify.app/widget.js"
  data-api-key="nkt_live_..."
  data-domain="tax"
  data-lang="bm"
  data-theme="light"
  data-white-label="false"></script>
```

## Web dashboard

`/developer` — key management, usage chart, code examples.
