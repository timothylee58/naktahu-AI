import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { I18nProvider } from '@/lib/i18n';
import { PageTransition } from '@/components/PageTransition';
import { ServiceWorkerRegistration } from '@/components/ServiceWorkerRegistration';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full h-full flex flex-col bg-zinc-50">
        <I18nProvider>
          <PageTransition>{children}</PageTransition>
        </I18nProvider>
        <ServiceWorkerRegistration />
      </body>
    </html>
  );
}
