import type { Metadata, Viewport } from 'next';
import { Inter, Plus_Jakarta_Sans, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';
import { I18nProvider } from '@/lib/i18n';
import { ThemeProvider } from '@/lib/theme';
import { PageTransition } from '@/components/PageTransition';
import { ServiceWorkerRegistration } from '@/components/ServiceWorkerRegistration';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { SeasonalBanner } from '@/components/SeasonalBanner';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  display: 'swap',
});

// Display face for headlines — some character without tipping into
// geometric/techy (Space Grotesk et al fight the "official/trustworthy"
// feeling this product needs). Falls back to Inter for CJK text.
const displaySans = Plus_Jakarta_Sans({
  variable: '--font-display-sans',
  subsets: ['latin'],
  display: 'swap',
});

// Utility/citation face — used specifically for source citations and
// document references (agency abbreviations, dates, reference numbers).
// Monospace reads as "data/record", reinforcing verified-fact vs.
// conversational AI text.
const plexMono = IBM_Plex_Mono({
  variable: '--font-mono-plex',
  subsets: ['latin'],
  weight: ['500', '600'],
  display: 'swap',
});

/**
 * Absolute base for OG/Twitter asset URLs.
 *
 * Without this Next.js falls back to http://localhost:3000, and the built
 * HTML really does ship `og:image=http://localhost:3000/og-image.png` — a
 * URL no crawler can fetch, so the share card silently never renders. That
 * fallback is only auto-populated on Vercel; this project deploys to
 * Netlify, so it has to be set explicitly.
 *
 * Falls back to naktahu.my (the primary domain, matching the existing
 * hardcoded fallback in developer/page.tsx) — set NEXT_PUBLIC_SITE_URL
 * explicitly on Netlify regardless, since a code fallback can't know
 * which of naktahu.my / naktahu.netlify.app a given deploy is actually
 * served from.
 */
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://naktahu.my';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: 'NakTahu — Soal tentang kerajaan',
  description:
    'Tanya soalan berkaitan perkhidmatan kerajaan Malaysia dengan NakTahu AI.',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'NakTahu',
  },
  icons: {
    icon: [
      { url: '/icons/icon.svg', type: 'image/svg+xml' },
      { url: '/icons/icon-32.png', sizes: '32x32', type: 'image/png' },
      { url: '/icons/icon-16.png', sizes: '16x16', type: 'image/png' },
    ],
    apple: { url: '/icons/apple-touch-icon.png', sizes: '180x180' },
  },
  // Share card. Regenerate with apps/web/scripts/generate-og-image.py when
  // the brand changes — it is a committed static asset, not a build step.
  openGraph: {
    type: 'website',
    siteName: 'naktahu.my',
    locale: 'ms_MY',
    title: 'naktahu.my — Ilmu tempatan, jawapan seketika.',
    description:
      'Jawapan bersumber rasmi untuk soalan kerajaan Malaysia — LHDN, KWSP, SSM, PERKESO, KKM, JPN.',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'naktahu.my — jawapan bersumber rasmi untuk soalan kerajaan Malaysia',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'naktahu.my — Ilmu tempatan, jawapan seketika.',
    description:
      'Jawapan bersumber rasmi untuk soalan kerajaan Malaysia — LHDN, KWSP, SSM, PERKESO, KKM, JPN.',
    images: ['/og-image.png'],
  },
};

export const viewport: Viewport = {
  themeColor: '#3B5BFF',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ms"
      className={`${inter.variable} ${displaySans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full h-full flex flex-col bg-zinc-50 font-sans">
        <I18nProvider>
          <ThemeProvider>
            <ErrorBoundary>
              {/* Site-wide, above every page's own layout — a shrink-to-fit
                  block sibling to PageTransition's flex-1, so it just pushes
                  content down slightly rather than fighting any page's own
                  full-height flex structure (e.g. /chat's header+sidebar
                  layout). Self-gates on a date window; renders nothing
                  outside it or once dismissed. */}
              <SeasonalBanner />
              <PageTransition>{children}</PageTransition>
            </ErrorBoundary>
          </ThemeProvider>
        </I18nProvider>
        <ServiceWorkerRegistration />
      </body>
    </html>
  );
}
