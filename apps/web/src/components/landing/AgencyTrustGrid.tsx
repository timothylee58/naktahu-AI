'use client';

import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

// Real Malaysian government agencies whose official guidance the RAG
// pipeline's document_chunks corpus is sourced from (see
// apps/api/scripts/sources.py) — descriptive labels only, no fabricated
// "live" counts or metrics, since this repo doesn't have per-agency
// ingestion stats to show honestly.
const AGENCIES = [
  { abbr: 'LHDN', descKey: 'landing.trust.lhdn.desc' },
  { abbr: 'KWSP', descKey: 'landing.trust.kwsp.desc' },
  { abbr: 'SSM', descKey: 'landing.trust.ssm.desc' },
  { abbr: 'PERKESO', descKey: 'landing.trust.perkeso.desc' },
  { abbr: 'KKM', descKey: 'landing.trust.kkm.desc' },
  { abbr: 'JPN', descKey: 'landing.trust.jpn.desc' },
] as const;

interface AgencyTrustGridProps {
  isDark?: boolean;
}

export function AgencyTrustGrid({ isDark = true }: AgencyTrustGridProps) {
  const { t } = useI18n();
  const cardClass = isDark
    ? 'bg-white/5 border-white/10 hover:border-white/20'
    : 'bg-white border-zinc-200 shadow-sm hover:shadow-md';
  const abbrClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const descClass = isDark ? 'text-zinc-400' : 'text-zinc-600';

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4 max-w-5xl mx-auto w-full">
      {AGENCIES.map((agency, i) => (
        <motion.div
          key={agency.abbr}
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.05, duration: 0.4 }}
          whileHover={{ y: -3 }}
          className={`flex flex-col items-center gap-1.5 text-center border rounded-xl px-3 py-4 transition-all duration-200 ${cardClass}`}
        >
          <span className={`text-sm font-bold tracking-wide locale-nowrap ${abbrClass}`}>
            {agency.abbr}
          </span>
          <span className={`text-[11px] leading-snug locale-text-balance ${descClass}`}>
            {t(agency.descKey)}
          </span>
        </motion.div>
      ))}
    </div>
  );
}
