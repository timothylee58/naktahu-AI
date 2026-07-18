---
name: ship
description: Preflight-verify, commit, push, and PR a change the NakTahu way. Use before any commit/push in this repo — runs the full local gate (pytest, typecheck, two-mains check, i18n check, lockfile hygiene), then applies the branch/PR protocol including the merged-branch restart.
---

# Ship a change

Run every step in order. Do not skip a step because the diff "looks small" — the traps this catches (CLAUDE.md §4) all came from small diffs.

## 1. Scope the diff

```bash
git status --short && git diff --stat
```

- Revert lockfile noise unless you intentionally changed deps: `git checkout -- package-lock.json`
- Confirm nothing staged references a secret value (env var *names* only).

## 2. Backend gate (skip only if no `apps/api/` files changed)

```bash
cd apps/api && python -m pytest -q
```

- If imports fail on missing deps, run `pip install -e ".[dev]"` once and retry.
- If ONLY the two known flakes fail (`test_auth.py::test_anonymous_query_rate_limit_31st_returns_429_with_retry_after`, `::test_authenticated_query_uses_user_bucket`) AND the diff doesn't touch auth/rate-limiting: re-run them in isolation, then proceed and name them in your report. Any other failure blocks the ship.
- **Two-mains check** — if any router was added or its mounting touched:
  ```bash
  grep -n "include_router" apps/api/main.py apps/api/app/main.py
  ```
  Every user-facing router must appear in BOTH lists. A miss here ships a feature that passes tests but doesn't exist in production.
- New migration file? Confirm it's numbered one above the current max in `infra/supabase/migrations/`, and add "paste `infra/supabase/migrations/NNN_*.sql` into the Supabase SQL editor" to the PR body draft.

## 3. Frontend gate (skip only if no `apps/web/` files changed)

```bash
npm run typecheck
```

- If deps are missing, `npm install --legacy-peer-deps`, then re-revert the lockfile.
- If you touched `apps/web/src/lib/i18n/index.tsx` or added `t('...')` calls: for each new key, grep `index.tsx` and confirm it exists in all three language blocks (BM/EN/ZH).
- Grep your changed files for `console.log` and `: any` — both must be absent.

## 4. Commit

- Imperative subject; body says why. If the commit addresses or rejects a bot-review finding, say which and why (rejections need the concrete failure scenario).
- Never mention model identifiers in commit messages or PR text.

## 5. Branch protocol (decide BEFORE pushing)

Check the designated branch's PR state (GitHub MCP: `list_pull_requests` filtered by head branch):

- **PR merged/closed** → the branch is finished. First check for commits not yet in main:
  ```bash
  git fetch origin main && git log origin/main..HEAD --oneline
  ```
  - If empty (only merged history): `git checkout -B <branch> origin/main` and start fresh. `--force-with-lease` on push is fine here — nothing is lost.
  - If NOT empty (you already committed new work): `git rebase origin/main` instead — never `checkout -B`, which would discard those commits.
- **PR open** → continue on the branch, and explicitly tell the user the open PR now carries both changes.
- **No PR** → normal push, then open one.

## 6. Push and PR

```bash
git push -u origin <branch>
```

Retry network failures 4× with 2s/4s/8s/16s backoff. Then, if no open PR exists for the branch, create one as **draft** via GitHub MCP. PR body must cover: what changed, why, how verified (test counts, typecheck), and required manual steps (migrations to paste, env vars to set, webhook config).

## 7. Report

Tell the user: what shipped, PR number/URL, honest test results (flakes named), and the manual steps that remain. Expect and ignore: Netlify "canceled" on backend-only diffs, CodeRabbit draft-skip, Bugbot usage-limit failures.
