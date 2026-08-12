import type { Metadata, Viewport } from 'next';
import { Inter, Plus_Jakarta_Sans, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';
import { I18nProvider } from '@/lib/i18n';
import { ThemeProvider } from '@/lib/theme';
import { PageTransition } from '@/components/PageTransition';
import { ServiceWorkerRegistration } from '@/components/ServiceWorkerRegistration';
import { ErrorBoundary } from '@/components/ErrorBoundary';

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

export const metadata: Metadata = {
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
    icon: '/icons/icon.svg',
    apple: '/icons/icon.svg',
  },
};

export const viewport: Viewport = {
  themeColor: '#3B6FE0',
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
              <PageTransition>{children}</PageTransition>
            </ErrorBoundary>
          </ThemeProvider>
        </I18nProvider>
        <ServiceWorkerRegistration />
      </body>
    </html>
  );
}
