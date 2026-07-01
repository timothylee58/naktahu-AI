# AGENTS.md

## Cursor Cloud specific instructions

NakTahu AI is a monorepo with two runnable services plus optional local Redis. Standard commands live in `README.md` and `package.json`; only the non-obvious, environment-specific caveats are captured here.

### Services

| Service | Dir | Dev run command | Port |
|---|---|---|---|
| Web (Next.js 15) | `apps/web` | `npm run dev` (from repo root or `apps/web`) | 3000 |
| API (FastAPI + LangGraph) | `apps/api` | `/workspace/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` (run **from `apps/api`**) | 8000 |
| Redis (optional cache/rate-limit) | — | `redis-server --daemonize yes --save "" --appendonly no` | 6379 |

### Non-obvious caveats

- **Python runs in a venv at `/workspace/.venv`.** The startup update script installs backend deps there (`apps/api` is installed editable). Use `/workspace/.venv/bin/uvicorn` / `/workspace/.venv/bin/pytest` — do not rely on a system `uvicorn`/`pytest`, and there is no `mise`/`pyenv` here (system Python is 3.12, which satisfies `requires-python >=3.11`).
- **Run the API with working directory `apps/api`.** The canonical app is `app.main:app`, but it also imports top-level packages (`core`, `services`, `middleware`), so the process cwd must be `apps/api` for imports to resolve. `pytest` relies on `pythonpath = ["."]` in `pyproject.toml`, so run it from `apps/api` too.
- **Two API entrypoints exist.** `apps/api/app/main.py` (`app.main:app`) is the canonical/deployed app and degrades gracefully when Redis/Supabase/ILMU are unavailable. `apps/api/main.py` is a legacy app that **requires Redis at startup**; the pytest suite imports it with Redis/Supabase mocked (`tests/conftest.py`). Always run/serve `app.main:app`.
- **The app boots and works without any real secrets.** Missing `ILMU_API_KEY` / `ANTHROPIC_API_KEY` / Supabase creds do not crash it — the pipeline (router→guard→rag→analyst→synthesiser) still runs and streams an SSE response, but returns a low-confidence clarification / fallback answer instead of real cited content. For real cited answers, provide `ILMU_API_KEY` + Supabase creds (and seed the vector DB via `scripts/ingest/`) as Cursor secrets, then mirror them into `apps/api/.env` and `apps/web/.env.local`.
- **Env files are gitignored and must exist locally.** `apps/api/.env` and `apps/web/.env.local` are not committed. Placeholder dev versions are created during setup; if missing, copy from `apps/api/.env.example` and `apps/web/.env.local.example`. The web rewrite proxies `/api/v1/*` to `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- **Frontend installs need `--legacy-peer-deps`** (React 19 peer ranges). CI uses `npm ci --legacy-peer-deps`; using a plain `npm install` rewrites cosmetic `package-lock.json` metadata (`devOptional`→`dev`) — prefer `npm ci` to avoid lockfile churn.
- **Redis and `python3.12-venv` are preinstalled in the VM snapshot** (apt system packages), so the update script does not reinstall them. Redis is optional (the API degrades gracefully); start it with the command above if you want caching/rate-limiting active. Docker is **not** installed — do not use `infra/docker-compose.yml`; run the services directly instead.

### Checks

- Web: `npm run typecheck` and `npm run lint` (repo root).
- API: `pytest tests/ -q` from `apps/api` using the venv (`/workspace/.venv/bin/pytest`).
