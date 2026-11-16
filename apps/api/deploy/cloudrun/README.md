# Cloud Run deploy (apps/api)

Runs the existing `apps/api/Dockerfile` unchanged. Railway keeps serving until you cut over.

## One-time setup

1. Create an Upstash Redis database in a Singapore region and copy its `rediss://` URL.
2. `gcloud auth login` and pick a GCP project with billing enabled.
3. Create `.env.cloudrun` in this folder (git-ignored) with every name in `deploy.sh`'s `SECRET_VARS` and `PLAIN_VARS`.
   Copy the values from the Railway `@naktahu-ai` service variables; set `REDIS_URL` to the Upstash URL.

## Deploy

```bash
cd apps/api/deploy/cloudrun
GCP_PROJECT=<project-id> ./deploy.sh
```

The script prints the `*.run.app` URL. Check `GET <url>/health` before cutting over.

## Cutover checklist

1. `netlify.toml`: change `NEXT_PUBLIC_API_URL` in both the production and deploy-preview contexts, then redeploy the web app.
2. `apps/web/src/app/developer/page.tsx`: replace the hardcoded default API base URL.
3. Add the new origin to `CORS_ORIGINS` if the web host changes.
4. If Stripe or HitPay webhooks are configured, point them at the new URL and update `PUBLIC_API_URL`. Neither is set on the Railway service today.
5. Watch for a week, then delete the Railway `@naktahu-ai` and `Redis` services.

## Behaviour differences to expect

- `MIN_INSTANCES=0` (default) scales to zero, so the first request after idle has a cold start. Set `MIN_INSTANCES=1` to avoid it; an idle instance costs far less than an active one, but not nothing.
- The LangGraph checkpointer uses `DATABASE_URL` (Supabase), so sessions survive across Cloud Run instances. If `DATABASE_URL` is unset it falls back to per-process memory and confirmations will break when more than one instance runs.
- Rate limiting and the query cache use Redis on every request. Check Upstash's current command limits against your traffic.
- Prometheus and Grafana were removed from Railway, so `/metrics` is unused.

- `API_BACKEND_URL` is set on the Railway service but nothing in `apps/api` reads it (it only appears in the web example env), so the script does not carry it over.
