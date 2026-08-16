'use client';

import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

// Real Malaysian government agencies whose official guidance the RAG
// pipeline's document_chunks corpus is sourced from (see
// apps/api/scripts/sources.py) — badge, full name, and two qualitative
// coverage tags. Deliberately no "N+ documents indexed" style counts:
// this repo has no per-agency ingestion-count query anywhere, so a
// precise-looking number here would be fabricated, not a real live stat
// (see InteractiveAnswerPreview.tsx's module comment for the same
// reasoning applied to the confidence-% and hotline-number fields).
const AGENCIES = [
  { abbr: 'LHDN', nameKey: 'landing.trust.lhdn.name', descKey: 'landing.trust.lhdn.desc', tag2Key: 'landing.trust.lhdn.tag2' },
  { abbr: 'KWSP', nameKey: 'landing.trust.kwsp.name', descKey: 'landing.trust.kwsp.desc', tag2Key: 'landing.trust.kwsp.tag2' },
  { abbr: 'SSM', nameKey: 'landing.trust.ssm.name', descKey: 'landing.trust.ssm.desc', tag2Key: 'landing.trust.ssm.tag2' },
  { abbr: 'PERKESO', nameKey: 'landing.trust.perkeso.name', descKey: 'landing.trust.perkeso.desc', tag2Key: 'landing.trust.perkeso.tag2' },
  { abbr: 'KKM', nameKey: 'landing.trust.kkm.name', descKey: 'landing.trust.kkm.desc', tag2Key: 'landing.trust.kkm.tag2' },
  { abbr: 'JPN', nameKey: 'landing.trust.jpn.name', descKey: 'landing.trust.jpn.desc', tag2Key: 'landing.trust.jpn.tag2' },
] as const;

interface AgencyTrustGridProps {
  isDark?: boolean;
}

export function AgencyTrustGrid({ isDark = true }: AgencyTrustGridProps) {
  const { t } = useI18n();
  // One shared-border container instead of 6 individually-bordered floating
  // cards — the V7-reference pattern ("Pick your industry"'s bordered
  // comparison grid) applied here: a trust list of official sources reads
  // as one coherent register, not 6 separate loose tiles, and it's a direct
  // fix for the "same-size cards" default the design system's craft floor
  // flags. A subtle hover wash per cell stands in for the old per-card
  // border-brighten-on-hover, without needing grid-row-aware interior
  // divider lines (CSS `divide-x`/`divide-y` utilities aren't grid-aware —
  // they'd draw a rule on every item after the first in DOM order
  // regardless of row/column position, producing a wrong line at the start
  // of row 2; not worth the complexity for what's a subtle grouping cue).
  const containerClass = isDark ? 'border-white/10' : 'border-zinc-200 bg-white';
  const cellHoverClass = isDark ? 'hover:bg-white/[0.03]' : 'hover:bg-zinc-50/80';
  const badgeClass = isDark
    ? 'bg-nk-official/10 text-nk-official border-nk-official/40'
    : 'bg-nk-official/5 text-nk-official-dim border-nk-official/30';
  const nameClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const tagClass = isDark ? 'text-zinc-400' : 'text-zinc-600';

  return (
    <div
      className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 rounded-2xl border max-w-4xl mx-auto w-full overflow-hidden ${containerClass}`}
    >
      {AGENCIES.map((agency, i) => (
        <motion.div
          key={agency.abbr}
          initial={{ opacity: 0, y: 8 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.05, duration: 0.4 }}
          className={`flex flex-col gap-2 px-4 py-3.5 transition-colors duration-200 ${cellHoverClass}`}
        >
          <span className={`self-start inline-flex items-center border-2 border-double rounded-md px-2 py-0.5 text-[11px] font-mono font-bold uppercase tracking-wide locale-nowrap ${badgeClass}`}>
            {agency.abbr}
          </span>
          <span className={`text-sm font-semibold leading-snug locale-text-balance ${nameClass}`}>
            {t(agency.nameKey)}
          </span>
          <div className="flex flex-col gap-0.5 text-[11px]">
            <span className={`flex items-center gap-1 locale-text-balance ${tagClass}`}>
              <span aria-hidden>✓</span> {t(agency.descKey)}
            </span>
            <span className={`flex items-center gap-1 locale-text-balance ${tagClass}`}>
              <span aria-hidden>✓</span> {t(agency.tag2Key)}
            </span>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
