// Shared DSN validation for sentry.client.config.ts / sentry.edge.config.ts /
// sentry.server.config.ts / next.config.ts.
//
// A plain `if (dsn)` truthiness check (the previous guard in all four
// files) let a placeholder value like "your_sentry_dsn_here" — left in a
// deploy env by copy-pasting an .env.example — through as "configured".
// Sentry.init() then attempted to parse it as a DSN and threw, breaking
// Sentry's own error reporting (and, via next.config.ts's withSentryConfig
// wrapping, the build itself) instead of just silently staying disabled
// the way an unset var does.
//
// A real Sentry DSN is always `https://<key>@<host>/<project-id>` — reject
// anything that doesn't at least match that shape rather than trying to
// enumerate every placeholder string someone might paste in.
const SENTRY_DSN_PATTERN = /^https:\/\/[a-f0-9]+@[a-z0-9.-]+\/\d+$/i;

export function isValidSentryDsn(dsn: string | undefined): dsn is string {
  return !!dsn && SENTRY_DSN_PATTERN.test(dsn.trim());
}
