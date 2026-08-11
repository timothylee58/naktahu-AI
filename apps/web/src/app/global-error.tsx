'use client';

// Next.js's top-level error boundary — the only one that can catch a
// rendering error thrown by the root layout itself (a regular error.tsx
// can't, since it renders *inside* the layout). Required reading for
// Sentry's Next.js instrumentation: without this file, an uncaught error
// during root-layout render skips Sentry entirely and the user just sees
// Next's default unstyled crash screen.
//
// This replaces the root <html>/<body> (the root layout is gone by the
// time this renders), so it can't reach useI18n/ThemeProvider/etc. — kept
// deliberately static and dependency-free, in both languages inline
// rather than through the i18n key table.

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          background: '#0A0F1E',
          color: '#fff',
          padding: '1.5rem',
        }}
      >
        <div style={{ maxWidth: 420, textAlign: 'center' }}>
          <p style={{ fontSize: '2rem', marginBottom: '0.5rem' }} aria-hidden>
            ⚠️
          </p>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Something went wrong / Sesuatu tidak kena
          </h1>
          <p style={{ fontSize: '0.9rem', color: '#a1a1aa', marginBottom: '1.5rem' }}>
            NakTahu AI hit an unexpected error. Please try again.
            <br />
            NakTahu AI menghadapi ralat tidak dijangka. Sila cuba lagi.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              background: '#2563EB',
              color: '#fff',
              border: 'none',
              borderRadius: '9999px',
              padding: '0.65rem 1.5rem',
              fontSize: '0.9rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Try again / Cuba lagi
          </button>
        </div>
      </body>
    </html>
  );
}
