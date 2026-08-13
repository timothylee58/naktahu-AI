# Contributing to NakTahu AI

Thanks for your interest. This document covers the mechanics — how to get the
project running, what CI will check, and how to shape a PR. The *conventions*
(and the reasoning behind the load-bearing ones) live in two other places, and
both are worth reading before your first change:

- **[`README.md`](README.md#contributing)** — architecture, quick start, and the
  short list of non-negotiable rules.
- **[`CLAUDE.md`](CLAUDE.md)** — the full operating manual, including a "Traps"
  section documenting mistakes that have already cost real debugging time. Every
  entry there exists because someone hit it.

---

## Getting set up

Full instructions are in [README § Quick start](README.md#quick-start). The short
version:

```bash
# Frontend
npm install --legacy-peer-deps
npm run dev --workspace=apps/web

# Backend
cd apps/api
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

You need a `.env.local` (web) and `.env` (api) — see
[README § Environment variable reference](README.md#environment-variable-reference)
for the full table. The app boots in a degraded mode without Supabase or Redis,
so you can work on most things without every credential.

---

## Before you open a PR

Run what CI runs. All of it is fast except the eval suite, which is still under
a minute:

```bash
npm run typecheck              # from repo root — tsc --noEmit
npm run build --workspace=apps/web

cd apps/api
python -m pytest tests/ -q     # unit + integration suite
python -m pytest evals/ -q     # adversarial, language accuracy, domain coverage
python -m pyflakes main.py app/main.py routers app/routers services app/services \
                  middleware app/middleware app/agents app/orchestration tests evals
```

A few checks that aren't automated but that reviewers will look for:

- **New backend route?** Mount it in **both** `apps/api/main.py` *and*
  `apps/api/app/main.py`. Two FastAPI apps exist; the test suite imports one and
  Railway deploys the other, so a route in only one passes CI and doesn't exist
  in production. `grep -l "your_router" apps/api/main.py apps/api/app/main.py`
  must print both files.
- **New user-visible string?** Add it to all three language blocks (`bm`, `en`,
  `zh`) in `apps/web/src/lib/i18n/index.tsx`. Never hardcode UI copy.
- **New knowledge domain?** The canonical list appears in several places
  (`router_node`, `guard_node`, `scripts/ingest_feed.py`, the `valid_domain`
  CHECK constraint, the eval datasets). They have drifted apart before — change
  them together, in one PR.
- **`package-lock.json` churn?** `npm install` rewrites it with meaningless
  `devOptional` → `dev` changes. Run `git checkout -- package-lock.json` unless
  you actually changed dependencies.

---

## Database migrations

Migrations in `infra/supabase/migrations/` are **not applied automatically** by
any process. If your change needs one:

1. Number it one above the highest file on `origin/main` **at push time** — not
   on your branch. Parallel PRs have produced duplicate numbers before.
2. Make the backend degrade gracefully (return 503, don't crash) until it's
   applied.
3. Say clearly in the PR body which file a maintainer needs to paste into the
   Supabase SQL editor.

Never describe a migration as "applied" — you can't verify that from a PR.

---

## Pull requests

- Branch from `main`. Keep PRs scoped to one concern where you can.
- Write commit messages in the imperative mood, with a body explaining *why*
  rather than restating the diff.
- Say honestly how you verified the change. If tests fail, or you couldn't run
  something (no credentials, sandboxed network), say so — a PR that overstates
  its verification is worse than one that admits a gap.
- Automated reviewers (CodeRabbit, Cursor Bugbot) comment on most PRs. Their
  findings are frequently right and occasionally wrong. Check each against the
  actual code rather than batch-accepting; if you reject one, say what would
  break if it were applied.

---

## Data and content changes

This project answers questions about government services, so content accuracy is
a correctness concern, not an editorial one:

- **Citations must be real.** Only genuine `gov.my`-family URLs taken from chunk
  metadata. If a source URL doesn't exist, omit the citation entirely — never
  synthesise a plausible-looking one.
- **All ingested content passes the injection scan** in
  `app/middleware/sanitise.py`. No ingestion path is exempt.
- **Don't fabricate statistics, dates, or figures** in UI copy, eval fixtures, or
  marketing text. If a real number isn't available, describe the thing
  qualitatively instead of inventing a precise-looking one.

---

## Reporting security issues

Please don't open a public issue for a security vulnerability. Email
**privacy@naktahu.my** with details and we'll respond as quickly as we can.

---

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](LICENSE), the same license that covers this project.
