'use client';

import type { ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { LandingFooter } from '@/components/landing/LandingFooter';
import { useI18n } from '@/lib/i18n';
import { LANDING_TAGLINE_KEYS } from '@/lib/landing-taglines';
import { useTheme } from '@/lib/theme';

export interface LegalSection {
  id: string;
  title: string;
  content: ReactNode;
}

interface LegalLayoutProps {
  title: string;
  meta: ReactNode;
  intro?: ReactNode;
  sections: readonly LegalSection[];
}

// Typography for long-form body copy (lists, tables, sub-headings, inline
// links/code) in theme tokens, so legal pages read the same in light and
// dark instead of the old light-only zinc palette.
const PROSE =
  'text-base leading-relaxed text-nk-ink/80 [&_p]:mt-3 [&_p:first-child]:mt-0 ' +
  '[&_ul]:mt-3 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5 ' +
  '[&_h3]:mt-6 [&_h3]:font-semibold [&_h3]:text-nk-ink ' +
  '[&_strong]:font-semibold [&_strong]:text-nk-ink ' +
  '[&_a]:font-medium [&_a]:text-nk-official-text [&_a]:underline [&_a]:underline-offset-2 ' +
  '[&_code]:rounded [&_code]:bg-black/5 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-sm dark:[&_code]:bg-white/10 ' +
  '[&_table]:mt-3 [&_table]:w-full [&_table]:border-collapse [&_table]:text-left [&_table]:text-sm ' +
  '[&_th]:border-b [&_th]:border-[var(--nk-border)] [&_th]:py-2 [&_th]:pr-4 [&_th]:font-semibold [&_th]:text-nk-ink ' +
  '[&_td]:border-b [&_td]:border-[var(--nk-border)] [&_td]:py-2 [&_td]:pr-4';

/** Shared shell for long-form policy pages (/privacy, /accessibility):
 * site header + footer, one readable column, and an "On this page" index
 * that is a sticky sidebar on desktop and a collapsible list on mobile. */
export function LegalLayout({ title, meta, intro, sections }: LegalLayoutProps) {
  const { t } = useI18n();
  const { theme } = useTheme();
  const pageBg = theme === 'dark' ? 'bg-[#12151C]' : 'bg-nk-bg-warm';

  const toc = (
    <ol className="space-y-2 text-sm">
      {sections.map((s) => (
        <li key={s.id}>
          <a
            href={`#${s.id}`}
            className="block rounded text-nk-ink/70 transition-colors hover:text-nk-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official"
          >
            {s.title}
          </a>
        </li>
      ))}
    </ol>
  );

  return (
    <div className={`flex min-h-screen flex-col font-sans ${pageBg}`}>
      <LandingHeader />
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-12 focus:outline-none sm:px-6 sm:py-16">
        <div className="max-w-3xl">
          <h1 className="font-display text-3xl font-extrabold tracking-[-0.01em] text-nk-ink sm:text-4xl">{title}</h1>
          <p className="mt-2 text-sm text-nk-muted-aa">{meta}</p>
          {intro && <div className="mt-6 text-lg leading-relaxed text-nk-ink/80">{intro}</div>}
        </div>

        <details className="group mt-8 rounded-xl border border-[var(--nk-border)] bg-nk-card px-4 py-3 lg:hidden">
          <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold text-nk-ink">
            {t('legal.on_this_page')}
            <ChevronDown aria-hidden className="h-4 w-4 transition-transform group-open:rotate-180" />
          </summary>
          <nav aria-label={t('legal.on_this_page')} className="mt-3">
            {toc}
          </nav>
        </details>

        <div className="mt-10 grid gap-12 lg:grid-cols-[220px_minmax(0,1fr)]">
          <nav aria-label={t('legal.on_this_page')} className="hidden lg:block">
            <div className="sticky top-24">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-nk-muted-aa">{t('legal.on_this_page')}</p>
              {toc}
            </div>
          </nav>
          <div className="max-w-3xl space-y-12">
            {sections.map((s) => (
              <section key={s.id} aria-labelledby={s.id} className="scroll-mt-24">
                <h2 id={s.id} className="scroll-mt-24 font-display text-xl font-bold text-nk-ink sm:text-2xl">
                  {s.title}
                </h2>
                <div className={`mt-4 ${PROSE}`}>{s.content}</div>
              </section>
            ))}
          </div>
        </div>
      </main>
      <LandingFooter tagline={t(LANDING_TAGLINE_KEYS[0])} />
    </div>
  );
}
