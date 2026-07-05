'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useI18n } from '@/lib/i18n';

interface SiteNavLinksProps {
  variant: 'dark' | 'light';
  onNavigate?: () => void;
  layout?: 'vertical' | 'horizontal';
  showChatCta?: boolean;
}

const LINKS = [
  { href: '/about', key: 'nav.about' },
  { href: '/faq', key: 'nav.faq' },
  { href: '/pricing', key: 'nav.pricing' },
  { href: '/agents', key: 'nav.agents' },
] as const;

export function SiteNavLinks({
  variant,
  onNavigate,
  layout = 'vertical',
  showChatCta = false,
}: SiteNavLinksProps) {
  const { t } = useI18n();
  const pathname = usePathname();
  const isDark = variant === 'dark';

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
      ? 'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors locale-nowrap'
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
      <Link
        href="/"
        onClick={onNavigate}
        className={`${itemClass} ${linkClass('/')}`}
      >
        {t('nav.home')}
      </Link>
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          onClick={onNavigate}
          className={`${itemClass} ${linkClass(link.href)}`}
        >
          {t(link.key)}
        </Link>
      ))}
    </nav>
  );
}
