'use client';

import Link from 'next/link';
import type { User } from '@supabase/supabase-js';
import { useI18n } from '@/lib/i18n';
import {
  WIRED_AGENTS,
  agentDescKey,
  agentPlanKey,
  agentTitleKey,
} from '@/lib/agents';

interface SidebarAgentsNavProps {
  user: User | null;
  isDark: boolean;
  navLinkClass: string;
  dividerClass: string;
  onClose?: () => void;
  compact?: boolean;
}

export function SidebarAgentsNav({
  user,
  isDark,
  navLinkClass,
  dividerClass,
  onClose,
  compact = false,
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
      <div className={`my-2 border-t ${dividerClass}`} />
      <p className={sectionLabelClass}>{t('nav.agents')}</p>
      <Link
        href="/agents"
        onClick={onClose}
        className={`px-3 py-2 rounded-lg text-sm font-semibold transition-colors locale-nowrap ${navLinkClass}`}
      >
        {t('agents.hub.link')}
      </Link>
      {WIRED_AGENTS.map((agent) => (
        <Link
          key={agent.slug}
          href={agent.href}
          onClick={onClose}
          className={`px-3 py-2 rounded-lg text-sm transition-colors locale-nowrap flex flex-col gap-0.5 ${navLinkClass}`}
          title={compact ? undefined : t(agentDescKey(agent.slug))}
        >
          <span className="flex items-center gap-2">
            <span className="font-medium">{t(agentTitleKey(agent.slug))}</span>
            {agent.badgeKey ? (
              <span className="text-[9px] font-bold uppercase tracking-wide text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded-full">
                {t(`agents.badge.${agent.badgeKey}`)}
              </span>
            ) : null}
          </span>
          {!compact && (
            <span className={`text-[10px] ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
              {t(agentPlanKey(agent.planKey))}
            </span>
          )}
        </Link>
      ))}
    </>
  );
}
