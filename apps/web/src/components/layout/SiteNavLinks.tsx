'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
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
const LINKS = [
  { href: '/about', key: 'nav.about', emoji: 'ℹ️', group: 'ai' },
  { href: '/faq', key: 'nav.faq', emoji: '❓', group: 'ai' },
  { href: '/pricing', key: 'nav.pricing', emoji: '💳', group: 'ai' },
  { href: '/developer', key: 'nav.developer', emoji: '🔌', group: 'ai' },
  { href: '/agents', key: 'nav.agents', emoji: '🤖', group: 'ai' },
  { href: '/warung-watch', key: 'nav.warung_watch', emoji: '🍜', group: 'community' },
] as const;

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
  // Emoji prefixes are a sidebar-only affordance — the horizontal landing
  // header (LandingHeader) uses this same component and keeps its plain
  // text-only look.
  const showEmoji = layout === 'vertical';
  // Group divider is a vertical-sidebar-only affordance too — the horizontal
  // landing header's flat pill row has no room for a section label and
  // isn't the primary app nav this distinction matters most for.
  const showGroups = layout === 'vertical';
  const aiLinks = visibleLinks.filter((link) => link.group === 'ai');
  const communityLinks = visibleLinks.filter((link) => link.group === 'community');

  const linkClass = (href: string, emphasized = false) => {
    const active = pathname === href || (href !== '/' && pathname.startsWith(href));
    if (emphasized) {
      return isDark
        ? 'border-blue-500/40 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20'
        : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100';
    }
    if (active) {
      return isDark
        ? 'bg-white/10 text-white'
        : 'bg-zinc-100 text-zinc-900';
    }
    return isDark
      ? 'text-zinc-300 hover:text-white hover:bg-white/10'
      : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100';
  };

  const base =
    layout === 'horizontal'
      ? 'flex flex-wrap items-center gap-1'
      : 'flex flex-col gap-0.5';

  const itemClass =
    layout === 'horizontal'
      ? 'px-3 py-1.5 rounded-lg text-lg font-bold transition-colors locale-nowrap'
      : 'px-3 py-2 rounded-lg text-sm font-medium transition-colors locale-nowrap';

  return (
    <nav className={base}>
      {showChatCta && (
        <Link
          href="/chat"
          onClick={onNavigate}
          className={`${itemClass} border ${linkClass('/chat', true)}`}
        >
          {t('nav.try_question')}
        </Link>
      )}
      {!hideHome && (
        <Link
          href="/"
          onClick={onNavigate}
          className={`${itemClass} ${linkClass('/')}`}
        >
          {showEmoji && <span aria-hidden="true">🏠 </span>}
          {t('nav.home')}
        </Link>
      )}
      {showGroups ? (
        <>
          {!hideHome && (
            <span
              className={`px-3 pt-1 pb-1 text-[10px] font-semibold uppercase tracking-wider ${
                isDark ? 'text-zinc-500' : 'text-zinc-400'
              }`}
            >
              {t('nav.group.ai')}
            </span>
          )}
          {aiLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={onNavigate}
              className={`${itemClass} ${linkClass(link.href)}`}
            >
              {showEmoji && <span aria-hidden="true">{link.emoji} </span>}
              {t(link.key)}
            </Link>
          ))}
          {communityLinks.length > 0 && (
            <>
              <span
                className={`px-3 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider ${
                  isDark ? 'text-zinc-500' : 'text-zinc-400'
                }`}
              >
                {t('nav.group.community')}
              </span>
              {communityLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={onNavigate}
                  className={`${itemClass} ${linkClass(link.href)} flex items-center gap-1.5`}
                >
                  {showEmoji && <span aria-hidden="true">{link.emoji} </span>}
                  {t(link.key)}
                  {/* Live-pulse dot — signals "real-time crowd data", distinct
                      from the static-document AI agents above. */}
                  <span className="relative flex h-1.5 w-1.5 flex-shrink-0" aria-hidden>
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  </span>
                </Link>
              ))}
            </>
          )}
        </>
      ) : (
        visibleLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            onClick={onNavigate}
            className={`${itemClass} ${linkClass(link.href)}`}
          >
            {showEmoji && <span aria-hidden="true">{link.emoji} </span>}
            {t(link.key)}
          </Link>
        ))
      )}
    </nav>
  );
}
