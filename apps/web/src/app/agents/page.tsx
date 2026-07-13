'use client';

import Link from 'next/link';
import { useI18n } from '@/lib/i18n';
import {
  WIRED_AGENTS,
  agentDescKey,
  agentPlanKey,
  agentTitleKey,
} from '@/lib/agents';

export default function AgentsHubPage() {
  const { t } = useI18n();

  return (
    <main className="min-h-screen bg-zinc-50">
      <header className="bg-white border-b border-zinc-200 px-4 py-3 flex items-center gap-3">
        <Link href="/chat" className="text-sm text-blue-600 hover:underline">
          ← {t('nav.home')}
        </Link>
        <h1 className="text-lg font-bold text-zinc-900">{t('agents.hub.title')}</h1>
      </header>
      <div className="max-w-3xl mx-auto px-4 py-8 grid gap-4">
        <p className="text-sm text-zinc-600">{t('agents.hub.subtitle')}</p>
        {WIRED_AGENTS.map((agent) => (
          <Link
            key={agent.slug}
            href={agent.href}
            className="block bg-white border border-zinc-200 rounded-2xl p-5 hover:border-blue-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between gap-2">
              <h2 className="font-semibold text-zinc-900">{t(agentTitleKey(agent.slug))}</h2>
              <span className="text-[10px] font-bold uppercase tracking-wide text-zinc-500 bg-zinc-100 px-2 py-0.5 rounded-full locale-nowrap">
                {t(agentPlanKey(agent.planKey))}
              </span>
            </div>
            <p className="text-sm text-zinc-600 mt-1">{t(agentDescKey(agent.slug))}</p>
            {agent.badgeKey ? (
              <span className="inline-block mt-2 text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
                {t(`agents.badge.${agent.badgeKey}`)}
              </span>
            ) : null}
          </Link>
        ))}
      </div>
    </main>
  );
}
