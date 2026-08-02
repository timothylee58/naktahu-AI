'use client';

import Link from 'next/link';
import type { User } from '@supabase/supabase-js';
import { useI18n } from '@/lib/i18n';

interface SidebarAgentsNavProps {
  user: User | null;
  isDark: boolean;
  navLinkClass: string;
  dividerClass: string;
  onClose?: () => void;
}

export function SidebarAgentsNav({
  user,
  isDark,
  navLinkClass,
  dividerClass,
  onClose,
}: SidebarAgentsNavProps) {
  const { t } = useI18n();

  if (!user) {
    return null;
  }

  const sectionLabelClass = `text-xs font-semibold uppercase tracking-wider px-3 locale-nowrap ${
    isDark ? 'text-zinc-500' : 'text-zinc-400'
  }`;

  return (
    <>
      <p className={sectionLabelClass}>{t('nav.agents')}</p>
      <Link
        href="/agents"
        onClick={onClose}
        className={`px-3 py-2 rounded-lg text-sm font-semibold transition-colors locale-nowrap ${navLinkClass}`}
      >
        <span aria-hidden="true">🤖 </span>{t('agents.hub.link')}
      </Link>
    </>
  );
}
