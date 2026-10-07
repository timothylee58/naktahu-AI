import * as Sentry from "@sentry/nextjs";
import { isValidSentryDsn } from "@/lib/sentry-dsn";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (isValidSentryDsn(dsn)) {
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV,
    tracesSampleRate: 0.2,
  });
}
