'use client';

import Link from 'next/link';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

// Next.js's fallback 404 handler for any route that doesn't match a page —
// required so static-generation doesn't fall back to Next's default
// unstyled "404 | This page could not be found" screen. Unlike
// global-error.tsx, this renders *inside* the root layout (ThemeProvider/
// I18nProvider are already mounted), so it can use the normal hooks.
export default function NotFound() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const pageClass = isDark
    ? 'bg-[#12151C] text-white'
    : 'bg-zinc-50 text-zinc-900';
  const mutedText = isDark ? 'text-zinc-400' : 'text-zinc-600';

  return (
    <div className={`flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center ${pageClass}`}>
      <p className="text-5xl font-bold text-nk-official" aria-hidden>
        404
      </p>
      <h1 className="font-display text-lg font-semibold locale-text-balance">{t('not_found.title')}</h1>
      <p className={`max-w-sm text-sm locale-text-balance ${mutedText}`}>{t('not_found.desc')}</p>
      <Link
        href="/"
        className="mt-2 inline-flex items-center gap-2 rounded-full bg-nk-official px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-nk-official-dim locale-nowrap"
      >
        {t('not_found.cta')}
      </Link>
    </div>
  );
}
