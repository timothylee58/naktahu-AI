'use client';

import Link from 'next/link';
import { useI18n } from '@/lib/i18n';
import { MakaKamiBadge } from '@/components/layout/MakaKamiBadge';

const GITHUB_URL = 'https://github.com/timothylee58/naktahu-AI';

interface LandingFooterProps {
  tagline: string;
}

// "Who runs this" footer in the government-site style: identity, sourcing
// policy and the standard links, so a first-time visitor can tell who is
// behind the answers before trusting one.
export function LandingFooter({ tagline }: LandingFooterProps) {
  const { t } = useI18n();
  const linkClass = 'text-nk-ink/80 transition-colors hover:text-nk-ink hover:underline underline-offset-2';

  return (
    <footer className="border-t border-[var(--nk-border)] bg-nk-card">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-4 py-12 text-sm sm:px-6 md:grid-cols-[1.2fr_1.2fr_0.8fr]">
        <div className="flex flex-col gap-2">
          <span className="font-display text-lg font-bold text-nk-ink locale-nowrap">NakTahu AI</span>
          <span className="text-nk-ink/80 locale-text-balance">{tagline}</span>
          <p className="mt-2 leading-relaxed text-nk-ink/80">{t('landing.footer.who')}</p>
        </div>
        <div className="flex flex-col gap-2">
          <h2 className="font-semibold text-nk-ink">{t('landing.footer.sourcing.title')}</h2>
          <p className="leading-relaxed text-nk-ink/80">{t('landing.footer.sourcing.desc')}</p>
        </div>
        <nav aria-label={t('landing.footer.nav_label')} className="flex flex-col gap-2">
          <h2 className="font-semibold text-nk-ink">{t('landing.footer.links')}</h2>
          <Link href="/about" className={linkClass}>{t('nav.about')}</Link>
          <Link href="/faq" className={linkClass}>{t('nav.faq')}</Link>
          <Link href="/privacy" className={linkClass}>{t('footer.privacy')}</Link>
          <Link href="/accessibility" className={linkClass}>{t('footer.accessibility')}</Link>
          <a href={`${GITHUB_URL}/issues`} target="_blank" rel="noopener noreferrer" className={linkClass}>
            {t('landing.footer.contact')} ↗
          </a>
        </nav>
      </div>
      <div className="border-t border-[var(--nk-border)]">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-4 px-4 py-6 text-xs text-nk-muted-aa sm:flex-row sm:px-6">
          <span className="max-w-xl text-center locale-text-balance sm:text-left">{t('landing.footer.disclaimer')}</span>
          <MakaKamiBadge />
        </div>
      </div>
    </footer>
  );
}
