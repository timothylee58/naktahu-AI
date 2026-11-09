'use client';

import { useId, useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

// Deliberately NOT the MYDS/USWDS "official government website" masthead:
// NakTahu is independent, so this strip states that outright and explains
// where answers come from, instead of borrowing an official banner's
// authority it doesn't have.
export function TrustStrip() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <div className="border-b border-[var(--nk-border)] bg-nk-card text-xs text-nk-ink/80">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-2 gap-y-1 px-4 py-1.5 sm:px-6">
        <ShieldCheck aria-hidden className="h-3.5 w-3.5 shrink-0 text-nk-official-text" />
        <span className="locale-text-balance">{t('trust_strip.summary')}</span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((v) => !v)}
          className="h-7 gap-1 px-2 font-semibold text-nk-official-text underline-offset-2 hover:underline"
        >
          {t('trust_strip.how')}
          <ChevronDown aria-hidden className={cn('h-3.5 w-3.5 transition-transform', open && 'rotate-180')} />
        </Button>
      </div>
      <div id={panelId} hidden={!open} className="mx-auto max-w-6xl px-4 pb-4 sm:px-6">
        <div className="grid gap-4 pt-2 text-sm sm:grid-cols-2">
          <div>
            <p className="font-semibold text-nk-ink">{t('trust_strip.independent.title')}</p>
            <p className="mt-1 leading-relaxed">{t('trust_strip.independent.desc')}</p>
          </div>
          <div>
            <p className="font-semibold text-nk-ink">{t('trust_strip.sources.title')}</p>
            <p className="mt-1 leading-relaxed">
              {t('trust_strip.sources.desc')}{' '}
              <Link href="/about" className="font-semibold text-nk-official-text underline underline-offset-2">
                {t('trust_strip.learn_more')}
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
