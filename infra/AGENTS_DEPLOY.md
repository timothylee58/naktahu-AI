# Agent infrastructure — production deploy checklist

Configure these on **Railway** (`naktahu-api` and `naktahu-deadline-cron` services) and apply Supabase migrations before enabling agents in production.

## 1. Supabase migrations

Apply in order (Supabase SQL editor or `supabase db push`):

| Migration | Purpose |
|-----------|---------|
| `010_agents.sql` | Agent registry, sessions, runs, `generated_documents`, `deadline_schedule` |
| `011_grant_finder.sql` | Grant Finder agent seed |
| `012_storage_generated_documents.sql` | `generated-documents` storage bucket + RLS |

## 2. Railway env vars — `naktahu-api`

Copy shared values from your existing API service, then add:

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | **Yes** (multi-turn agents) | Supabase **direct** Postgres on port **5432** (not the transaction pooler on 6543). Example: `postgresql://postgres:[password]@db.your-project.supabase.co:5432/postgres` from Supabase → Project Settings → Database → Connection string → URI. LangGraph `AsyncPostgresSaver` creates checkpoint tables on startup via `setup()`. |
| `SUPABASE_STORAGE_BUCKET` | Yes | `generated-documents` (default in code) |
| `RESEND_API_KEY` | Yes (PDF email) | From [Resend](https://resend.com/api-keys). Domain must be verified. |
| `RESEND_FROM_EMAIL` | Yes | Verified sender, e.g. `NakTahu <noreply@naktahu.ai>` |
| `SUPABASE_URL` | Yes | Existing |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Existing — used for storage upload + signed URLs |
| `REDIS_URL` | Yes | Existing — daily quota + cache |
| `FREE_DAILY_QUERY_LIMIT` | Optional | Default `25` |

Without `DATABASE_URL`, agents fall back to in-memory checkpoints (lost on restart).

Without `RESEND_API_KEY`, Compliance Drafter still generates PDFs but skips email delivery.

## 3. Deadline Monitor cron — GitHub Actions

Runs on a GitHub-hosted runner via `.github/workflows/deadline-monitor.yml`,
**not** as a Railway service.

- Schedule: `0 18 * * *` (02:00 Malaysia Time), plus `workflow_dispatch` for
  manual/missed runs.
- Command: `python scripts/agents/deadline_monitor.py` from `apps/api`.

**Required GitHub repository secrets** (Settings → Secrets and variables →
Actions):

| Secret | Required | Notes |
|--------|----------|-------|
| `SUPABASE_URL` | Yes | Shared with other workflows |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Server-side only — never exposed to the frontend |
| `RESEND_API_KEY` | Yes | Email is the only alert delivery channel |
| `RESEND_FROM_EMAIL` | Yes | Verified sender in Resend |

Previously this was a Railway cron service (`apps/cron-deadline-monitor`).
That approach was abandoned after repeated failures: the service was never
reliably visible to `RAILWAY_TOKEN`, every service-name/ID resolution attempt
missed, and dashboard edits meant for it landed on the live API service's
Root Directory instead. Running it in Actions removes that whole class of
problem and keeps cron changes structurally unable to touch the API service.

## 4. Verify after deploy

1. **PostgresSaver** — API logs should show `checkpointer_postgres` (not `checkpointer_memory`).
2. **Storage** — Start Compliance Drafter, confirm PDF; check Supabase Storage → `generated-documents`.
3. **Resend** — Confirm PDF email arrives; check Resend dashboard for delivery status.
4. **Cron** — Railway → `naktahu-deadline-cron` → Deployments; after 02:00 MYT, logs should show `deadline_monitor_complete`.

## 5. Local development

```bash
# apps/api/.env
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL="NakTahu <onboarding@resend.dev>"
SUPABASE_STORAGE_BUCKET=generated-documents

# Run cron manually
cd apps/api && python scripts/agents/deadline_monitor.py
```
