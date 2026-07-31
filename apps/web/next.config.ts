import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Security headers applied to every route (augmented by Vercel headers in vercel.json)
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-XSS-Protection", value: "1; mode=block" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(self), geolocation=()",
          },
        ],
      },
    ];
  },

  // Proxy /api/v1/* to the FastAPI backend — mainly a local-dev convenience
  // (so a bare relative fetch('/api/v1/...') still reaches the backend
  // without NEXT_PUBLIC_API_URL set) and defense-in-depth if Netlify's
  // Next.js runtime honours it in production too. Production code must
  // NEVER rely on this alone, though: every fetch to the backend should
  // build an absolute URL via the shared API_BASE constant
  // (apps/web/src/lib/api-base.ts) instead of a bare relative path. This
  // comment previously (incorrectly) said "In production, Vercel rewrites
  // (vercel.json) handle this instead" — that was stale from before the
  // Vercel→Netlify migration; no vercel.json exists in this repo, and
  // relying on this rewrite alone in production is exactly what caused
  // /api/v1/history, /api/v1/transcribe, the deadline-monitor widget, and
  // every vertical-agent start/continue call to silently 404 in
  // production (fixed by giving them all an absolute URL instead).
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiUrl}/api/v1/:path*`,
      },
    ];
  },
};

// Wrap with Sentry only when NEXT_PUBLIC_SENTRY_DSN is set so local dev
// without a DSN still works without the @sentry/nextjs package being required
// at build time.
async function buildConfig(): Promise<NextConfig> {
  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) {
    return nextConfig;
  }
  try {
    const { withSentryConfig } = await import("@sentry/nextjs");
    return withSentryConfig(nextConfig, {
      silent: true,
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      widenClientFileUpload: true,
      sourcemaps: { disable: true },
      disableLogger: true,
    });
  } catch {
    // @sentry/nextjs not installed — degrade gracefully
    return nextConfig;
  }
}

export default buildConfig();
