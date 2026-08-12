'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, Info, HelpCircle, CreditCard, Plug, Bot, Soup, type LucideIcon } from 'lucide-react';
import { useI18n } from '@/lib/i18n';

interface SiteNavLinksProps {
  variant: 'dark' | 'light';
  onNavigate?: () => void;
  layout?: 'vertical' | 'horizontal';
  showChatCta?: boolean;
  /** Omit links from the nav (e.g. landing header defers pricing/agents to hero). */
  excludeHrefs?: readonly string[];
  hideHome?: boolean;
}

// "group" separates two different interaction models that shouldn't read as
// one flat feature list: 'ai' items are turn-based AI consultations (ask a
// question, get a structured/cited answer); 'community' is Warung Watch —
// crowd-sourced, real-time, browse-and-glance, no RAG/citations/credits.
// Mixing them undifferentiated sets the wrong expectation for what tapping
// Warung Watch actually does.
const LINKS: { href: string; key: string; Icon: LucideIcon; group: 'ai' | 'community' }[] = [
  { href: '/about', key: 'nav.about', Icon: Info, group: 'ai' },
  { href: '/faq', key: 'nav.faq', Icon: HelpCircle, group: 'ai' },
  { href: '/pricing', key: 'nav.pricing', Icon: CreditCard, group: 'ai' },
  { href: '/developer', key: 'nav.developer', Icon: Plug, group: 'ai' },
  { href: '/agents', key: 'nav.agents', Icon: Bot, group: 'ai' },
  { href: '/warung-watch', key: 'nav.warung_watch', Icon: Soup, group: 'community' },
];

export function SiteNavLinks({
  variant,
  onNavigate,
  layout = 'vertical',
  showChatCta = false,
  excludeHrefs = [],
  hideHome = false,
}: SiteNavLinksProps) {
  const { t } = useI18n();
  const pathname = usePathname();
  const isDark = variant === 'dark';
  const excluded = new Set(excludeHrefs);
  const visibleLinks = LINKS.filter((link) => !excluded.has(link.href));
  const isActive = (href: string) => pathname === href || (href !== '/' && pathname.startsWith(href));

  // Vertical layout (app sidebar) gets the full Cloudflare-style treatment:
  // icon + label row, a full-row background tint plus a colored left-edge
  // bar for the active item (a clearer "you are here" signal than bold text
  // alone), and a restrained icon set — thin, monochrome, only the active
  // item gets an accent color. Horizontal layout (landing header) stays a
  // plain text-only pill row.
  if (layout === 'vertical') {
    const aiLinks = visibleLinks.filter((link) => link.group === 'ai');
    const communityLinks = visibleLinks.filter((link) => link.group === 'community');

    const rowClass = (href: string, isCommunity = false) => {
      const active = isActive(href);
      const base = 'relative flex items-center gap-2.5 pl-3.5 pr-3 py-2 rounded-lg text-sm font-medium transition-colors locale-nowrap';
      if (active) {
        return `${base} ${isDark ? 'bg-white/5 text-white' : 'bg-zinc-100 text-zinc-900'}`;
      }
      return `${base} ${
        isDark
          ? 'text-zinc-300 hover:text-white hover:bg-white/5'
          : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50'
      } ${isCommunity ? '' : ''}`;
    };

    const iconClass = (href: string, isCommunity = false) => {
      const active = isActive(href);
      if (!active) return isDark ? 'text-zinc-500' : 'text-zinc-400';
      return isCommunity ? 'text-nk-community' : (isDark ? 'text-nk-official' : 'text-nk-official-dim');
    };

    const renderRow = (link: (typeof LINKS)[number]) => {
      const active = isActive(link.href);
      const isCommunity = link.group === 'community';
      return (
        <Link
          key={link.href}
          href={link.href}
          onClick={onNavigate}
          className={rowClass(link.href, isCommunity)}
        >
          {active && (
            <span
              aria-hidden
              className={`absolute left-0 top-1 bottom-1 w-[2.5px] rounded-full ${
                isCommunity ? 'bg-nk-community' : 'bg-nk-official'
              }`}
            />
          )}
          <link.Icon size={18} strokeWidth={1.75} className={`flex-shrink-0 ${iconClass(link.href, isCommunity)}`} aria-hidden />
          <span className="flex-1 min-w-0 truncate">{t(link.key)}</span>
          {isCommunity && (
            // Live-pulse dot — signals "real-time crowd data", distinct
            // from the static-document AI agents above.
            <span className="relative flex h-1.5 w-1.5 flex-shrink-0" aria-hidden>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-nk-community opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-nk-community" />
            </span>
          )}
        </Link>
      );
    };

    return (
      <nav className="flex flex-col gap-0.5">
        {showChatCta && (
          <Link
            href="/chat"
            onClick={onNavigate}
            className={`flex items-center gap-2.5 pl-3.5 pr-3 py-2 rounded-lg text-sm font-medium border transition-colors locale-nowrap ${
              isDark
                ? 'border-nk-official/40 bg-nk-official/10 text-nk-official hover:bg-nk-official/20'
                : 'border-nk-official/30 bg-nk-official/5 text-nk-official-dim hover:bg-nk-official/10'
            }`}
          >
            {t('nav.try_question')}
          </Link>
        )}
        {!hideHome && (
          <Link href="/" onClick={onNavigate} className={rowClass('/')}>
            {isActive('/') && (
              <span aria-hidden className={`absolute left-0 top-1 bottom-1 w-[2.5px] rounded-full bg-nk-official`} />
            )}
            <Home size={18} strokeWidth={1.75} className={`flex-shrink-0 ${iconClass('/')}`} aria-hidden />
            <span className="flex-1 min-w-0 truncate">{t('nav.home')}</span>
          </Link>
        )}

        {aiLinks.length > 0 && (
          <>
            <span
              className={`px-3.5 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider ${
                isDark ? 'text-zinc-500' : 'text-zinc-400'
              }`}
            >
              {t('nav.group.ai')}
            </span>
            {aiLinks.map(renderRow)}
          </>
        )}

        {communityLinks.length > 0 && (
          <>
            {/* Hairline divider — a firmer boundary than the label alone
                between the two different interaction models. */}
            <div className={`my-2 border-t ${isDark ? 'border-white/5' : 'border-zinc-100'}`} aria-hidden />
            <span
              className={`px-3.5 pb-1 text-[11px] font-semibold uppercase tracking-wider ${
                isDark ? 'text-zinc-500' : 'text-zinc-400'
              }`}
            >
              {t('nav.group.community')}
            </span>
            {communityLinks.map((link) => renderRow(link))}
          </>
        )}
      </nav>
    );
  }

  // Horizontal layout — landing header's plain text-only pill row, unchanged.
  const linkClass = (href: string, emphasized = false) => {
    const active = isActive(href);
    if (emphasized) {
      return isDark
        ? 'border-nk-official/40 bg-nk-official/10 text-nk-official hover:bg-nk-official/20'
        : 'border-nk-official/30 bg-nk-official/5 text-nk-official-dim hover:bg-nk-official/10';
    }
    if (active) {
      return isDark ? 'bg-white/10 text-white' : 'bg-zinc-100 text-zinc-900';
    }
    return isDark
      ? 'text-zinc-300 hover:text-white hover:bg-white/10'
      : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100';
  };

  return (
    <nav className="flex flex-wrap items-center gap-1">
      {showChatCta && (
        <Link
          href="/chat"
          onClick={onNavigate}
          className={`px-3 py-1.5 rounded-lg text-lg font-bold border transition-colors locale-nowrap ${linkClass('/chat', true)}`}
        >
          {t('nav.try_question')}
        </Link>
      )}
      {!hideHome && (
        <Link href="/" onClick={onNavigate} className={`px-3 py-1.5 rounded-lg text-lg font-bold transition-colors locale-nowrap ${linkClass('/')}`}>
          {t('nav.home')}
        </Link>
      )}
      {visibleLinks.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          onClick={onNavigate}
          className={`px-3 py-1.5 rounded-lg text-lg font-bold transition-colors locale-nowrap ${linkClass(link.href)}`}
        >
          {t(link.key)}
        </Link>
      ))}
    </nav>
  );
}
