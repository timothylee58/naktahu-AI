'use client';

import type { ReactNode } from 'react';
import { ExternalLink } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { allOfficial, formatCheckedDate, latestChecked, sourceRows } from '@/lib/citations';
import type { Citation } from '@/lib/types';
import { cn } from '@/lib/utils';

function TierBadge({ tier, children }: { tier: 'official' | 'community'; children: ReactNode }) {
  // The word is part of the badge so colour is never the only signal.
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-0.5 text-xs font-semibold',
        tier === 'official'
          ? 'bg-[var(--nk-fill-official)] text-nk-official-text'
          : 'bg-[var(--nk-fill-community)] text-nk-community-text',
      )}
    >
      <span aria-hidden className={cn('h-1.5 w-1.5 rounded-full', tier === 'official' ? 'bg-nk-official' : 'bg-nk-community')} />
      {children}
    </span>
  );
}

// Provenance card under a finished answer. Everything here comes from the
// citation metadata the backend streams: a row without a real URL is dropped,
// the Official/Community badge comes from the stored source_tier (and is
// absent when the tier is unknown), and the date is the newest retrieved_at,
// shown only when one exists.
export function AnswerSources({ citations }: { citations: Citation[] }) {
  const { t, locale } = useI18n();
  const rows = sourceRows(citations);
  if (rows.length === 0) return null;
  const checked = latestChecked(citations);

  return (
    <div className="flex flex-col gap-2">
      <section
        aria-label={t('answer.sources')}
        className="rounded-2xl border border-[var(--nk-border)] bg-nk-card p-3.5 text-nk-ink"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-[11px] font-bold uppercase tracking-[0.08em] text-nk-muted-aa">{t('answer.sources')}</h3>
            {allOfficial(rows) && <TierBadge tier="official">{t('answer.official')}</TierBadge>}
          </div>
          {checked && (
            <span className="font-mono text-xs text-nk-muted-aa">
              {t('answer.checked').replace('{date}', formatCheckedDate(checked, locale))}
            </span>
          )}
        </div>

        <ul className="mt-2.5 flex flex-col gap-2.5">
          {rows.map((r) => (
            <li key={r.url} className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                {r.tier && (
                  <TierBadge tier={r.tier}>{t(r.tier === 'official' ? 'answer.badge.official' : 'answer.badge.community')}</TierBadge>
                )}
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-[13px] font-semibold hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official"
                >
                  {r.host}
                  <ExternalLink aria-hidden className="h-3 w-3 text-nk-muted-aa" />
                </a>
                <span className="min-w-0 truncate text-[13px] text-nk-muted-aa">{r.ministry}</span>
              </div>
              {r.tier === 'community' && (
                <p className="text-xs text-nk-community-text">{t('answer.communityNote')}</p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <p className="rounded-2xl border border-dashed border-[var(--nk-border)] px-3.5 py-2.5 text-[13px] leading-normal text-nk-muted-aa">
        <strong className="font-semibold text-nk-ink">{t('answer.scopeTitle')}</strong> {t('answer.scopeBody')}
      </p>
    </div>
  );
}
