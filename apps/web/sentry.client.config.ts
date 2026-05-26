import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV,
    // Capture 20 % of transactions for performance monitoring
    tracesSampleRate: 0.2,
    // Session replay — 10 % normal, 100 % on error
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    integrations: [Sentry.replayIntegration()],
    // Strip PII
    beforeSend(event: Sentry.ErrorEvent) {
      if (event.request?.cookies) delete event.request.cookies;
      return event;
    },
  });
}
