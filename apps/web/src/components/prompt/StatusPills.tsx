'use client';

import { ShieldCheck } from 'lucide-react';
import { useI18n } from '@/lib/i18n';

export function StatusPills({ lang }: { lang: string }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center gap-2 font-mono text-[11px] font-medium sm:flex-row sm:flex-wrap sm:justify-center sm:text-xs">
      <span className="inline-flex items-center gap-2 rounded-full border border-[var(--nk-pill-official-border)] bg-[var(--nk-pill-official-bg)] px-3 py-1.5 text-nk-official-text sm:px-3.5">
        <span aria-hidden className="h-[7px] w-[7px] rounded-full bg-nk-official" />
        {t('home.pill.engine').replace('{lang}', lang)}
      </span>
      <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--nk-pill-heritage-border)] bg-[var(--nk-pill-heritage-bg)] px-3 py-1.5 text-nk-heritage-text sm:px-3.5">
        <ShieldCheck aria-hidden className="h-3.5 w-3.5" />
        {t('home.pill.sources')}
      </span>
    </div>
  );
}
