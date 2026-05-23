'use client';

import { useI18n } from '@/lib/i18n';

export function LanguageToggle() {
  const { locale, setLocale, t } = useI18n();

  return (
    <button
      onClick={() => setLocale(locale === 'ms' ? 'en' : 'ms')}
      className="text-xs font-semibold bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-full px-3 py-1.5 transition-colors"
      aria-label={t('language')}
    >
      {locale === 'ms' ? 'EN' : 'BM'}
    </button>
  );
}
