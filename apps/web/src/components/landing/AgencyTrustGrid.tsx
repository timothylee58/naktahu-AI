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
//
// Icon, not logo: real ministry crests aren't used here on purpose. This
// product's own brand mark deliberately avoids reading as an official
// government seal (see NakTahuMark.tsx), and placing a real official logo
// next to that same product's UI carries the same risk in reverse — it
// can read as an implied partnership/endorsement this app doesn't have.
// Each icon below is generic geometry evoking the agency's function
// (a receipt for the tax authority, a shield for social security, ...),
// not a redrawn crest.
const AGENCIES = [
  { abbr: 'LHDN', nameKey: 'landing.trust.lhdn.name', descKey: 'landing.trust.lhdn.desc', tag2Key: 'landing.trust.lhdn.tag2', icon: 'receipt' },
  { abbr: 'KWSP', nameKey: 'landing.trust.kwsp.name', descKey: 'landing.trust.kwsp.desc', tag2Key: 'landing.trust.kwsp.tag2', icon: 'piggybank' },
  { abbr: 'SSM', nameKey: 'landing.trust.ssm.name', descKey: 'landing.trust.ssm.desc', tag2Key: 'landing.trust.ssm.tag2', icon: 'building' },
  { abbr: 'PERKESO', nameKey: 'landing.trust.perkeso.name', descKey: 'landing.trust.perkeso.desc', tag2Key: 'landing.trust.perkeso.tag2', icon: 'shield' },
  { abbr: 'KKM', nameKey: 'landing.trust.kkm.name', descKey: 'landing.trust.kkm.desc', tag2Key: 'landing.trust.kkm.tag2', icon: 'cross' },
  { abbr: 'JPN', nameKey: 'landing.trust.jpn.name', descKey: 'landing.trust.jpn.desc', tag2Key: 'landing.trust.jpn.tag2', icon: 'idcard' },
] as const;

type AgencyIcon = (typeof AGENCIES)[number]['icon'];

// One consistent stroke weight/viewBox across all six — a mismatched icon
// set (some filled, some outlined, different corner radii) reads as
// assembled rather than designed.
function Icon({ name, className }: { name: AgencyIcon; className?: string }) {
  const common = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className,
    'aria-hidden': true,
  };
  switch (name) {
    case 'receipt':
      return (
        <svg {...common}>
          <path d="M6 3.5h12v17l-2.2-1.4L14 20.5l-2-1.4-2 1.4-1.8-1.4L6 20.5v-17Z" />
          <path d="M9 8h6M9 11.5h6M9 15h3.5" />
        </svg>
      );
    case 'piggybank':
      return (
        <svg {...common}>
          <path d="M5 13a6 6 0 0 1 6-6h3.5a3.5 3.5 0 0 1 3.5 3.5v.5l2 1.5-2 1v1a2 2 0 0 1-2 2h-1v1.5h-2V17h-3v1.5H8V17a4 4 0 0 1-3-3.9V13Z" />
          <circle cx="9.5" cy="12" r="0.6" fill="currentColor" stroke="none" />
          <path d="M8 7.5 7 5.5" />
        </svg>
      );
    case 'building':
      return (
        <svg {...common}>
          <path d="M5 20.5V6l7-3 7 3v14.5" />
          <path d="M3.5 20.5h17" />
          <path d="M9.5 20.5V16h5v4.5" />
          <path d="M9 9.5h1.4M13.6 9.5H15M9 13h1.4M13.6 13H15" />
        </svg>
      );
    case 'shield':
      return (
        <svg {...common}>
          <path d="M12 3.5 5 6v5.5c0 4.6 3 7.9 7 9 4-1.1 7-4.4 7-9V6l-7-2.5Z" />
          <path d="M9 12l2 2 4-4.2" />
        </svg>
      );
    case 'cross':
      return (
        <svg {...common}>
          <rect x="3.5" y="3.5" width="17" height="17" rx="5" />
          <path d="M12 8v8M8 12h8" />
        </svg>
      );
    case 'idcard':
      return (
        <svg {...common}>
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <circle cx="8.5" cy="11" r="1.8" />
          <path d="M5.8 15.5c0-1.4 1.2-2.3 2.7-2.3s2.7.9 2.7 2.3" />
          <path d="M14.5 9.5h4M14.5 12.5h4M14.5 15.5h2.5" />
        </svg>
      );
  }
}

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
  const iconWrapClass = isDark
    ? 'bg-white/5 text-nk-official'
    : 'bg-nk-official/5 text-nk-official-dim';
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
          <div className="flex items-center gap-2">
            <span className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-lg ${iconWrapClass}`}>
              <Icon name={agency.icon} className="w-[18px] h-[18px]" />
            </span>
            <span className={`inline-flex items-center border-2 border-double rounded-md px-2 py-0.5 text-[11px] font-mono font-bold uppercase tracking-wide locale-nowrap ${badgeClass}`}>
              {agency.abbr}
            </span>
          </div>
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
