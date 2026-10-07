/**
 * Absolute base URL of the FastAPI backend (Railway in production, or a
 * local dev server). Every fetch to /api/v1/* must be built as
 * `${API_BASE}/api/v1/...` — a bare relative path (`fetch('/api/v1/...')`)
 * resolves against the frontend's OWN origin (Netlify), not the backend,
 * and silently 404s in production.
 *
 * This was previously redefined inline in five separate files (drift risk
 * realised: three other call sites — history.ts, DeadlineWidget.tsx,
 * useVoiceInput.ts, useAgentApi.ts — used a bare relative path instead and
 * were broken in production, e.g. "Failed to load history"). One shared
 * constant closes that class of bug going forward.
 *
 * next.config.ts also has a `rewrites()` proxy for `/api/v1/*` as a local
 * dev convenience (and defense-in-depth if Netlify's Next.js runtime
 * happens to honour it) — but production code must never depend on that
 * rewrite alone; always use this absolute-URL constant.
 */
export const API_BASE: string =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : '';
