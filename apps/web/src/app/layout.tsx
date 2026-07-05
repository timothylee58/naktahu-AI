import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
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
  themeColor: '#2563EB',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ms"
      className={`${inter.variable} h-full antialiased`}
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
