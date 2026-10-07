'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { agentTitleKey, agentDescKey } from '@/lib/agents';

// Only real, wired agents (apps/web/src/lib/agents.ts's WIRED_AGENTS) — no
// invented "LHDN Tax Relief Advisor"/"EPF Specialist" agents that don't
// exist as distinct products. Warung Watch isn't in WIRED_AGENTS (it's a
// standalone crowdsourced-data page, not an agent-registry entry), so it's
// listed separately below with its own href/copy instead of borrowing the
// agents.* i18n keys it doesn't have.
const SPOTLIGHT_SLUGS = ['sme-compliance-navigator', 'retrenchment-navigator', 'health-triage'] as const;

interface AgentSpotlightProps {
  isDark?: boolean;
}

export function AgentSpotlight({ isDark = true }: AgentSpotlightProps) {
  const { t } = useI18n();
  const cardClass = isDark
    ? 'bg-white/5 border-white/10 hover:border-white/20'
    : 'bg-white border-zinc-200 shadow-sm hover:shadow-md';
  const titleClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const descClass = isDark ? 'text-zinc-400' : 'text-zinc-600';
  const linkClass = isDark ? 'text-nk-official' : 'text-nk-official-dim';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 max-w-5xl mx-auto w-full">
      {SPOTLIGHT_SLUGS.map((slug, i) => (
        <motion.div
          key={slug}
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.06, duration: 0.4 }}
          whileHover={{ y: -4 }}
          className={`flex flex-col gap-3 border rounded-2xl p-5 transition-all duration-200 ${cardClass}`}
        >
          <h3 className={`font-semibold text-sm locale-nowrap ${titleClass}`}>
            {t(agentTitleKey(slug))}
          </h3>
          <p className={`text-xs leading-relaxed flex-1 locale-text-balance ${descClass}`}>
            {t(agentDescKey(slug))}
          </p>
          <Link href={`/agents/${slug}`} className={`text-xs font-semibold locale-nowrap ${linkClass}`}>
            {t('landing.hero.secondary_cta')} →
          </Link>
        </motion.div>
      ))}

      {/* Deliberately NOT styled like the three AI-agent cards above — Warung
          Watch is crowd-sourced/real-time browse-and-glance, not a "give
          input, get a cited AI answer" consultation, and an identical card
          in this row would misrepresent what tapping it does. Gold is the
          system-wide "community/crowd-sourced" color (vs. blue = "official
          source") — the same distinction now used in the sidebar nav and
          the citation-stamp component, so a user learns it once. */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: SPOTLIGHT_SLUGS.length * 0.06, duration: 0.4 }}
        whileHover={{ y: -4 }}
        className={`flex flex-col gap-3 border-2 border-dashed rounded-2xl p-5 transition-all duration-200 ${
          isDark ? 'bg-nk-community/5 border-nk-community/30 hover:border-nk-community/50' : 'bg-nk-community/5 border-nk-community/40 hover:border-nk-community/60'
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2 flex-shrink-0" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-nk-community opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-nk-community" />
          </span>
          <span className={`text-[10px] font-bold uppercase tracking-wide ${isDark ? 'text-nk-community' : 'text-nk-community-dim'}`}>
            {t('nav.group.community')}
          </span>
        </div>
        <h3 className={`font-semibold text-sm locale-nowrap ${titleClass}`}>{t('nav.warung_watch')}</h3>
        <p className={`text-xs leading-relaxed flex-1 locale-text-balance ${descClass}`}>
          {t('landing.spotlight.warung_watch.desc')}
        </p>
        <Link href="/warung-watch" className={`text-xs font-semibold locale-nowrap ${linkClass}`}>
          {t('landing.hero.secondary_cta')} →
        </Link>
      </motion.div>
    </div>
  );
}
