'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

// Same 5 concepts LandingFeatures.tsx used to render as 5 parallel
// icon+heading+text cards — replaced with a tab list driving one mockup
// panel (the V7/Fixa "tabbed showcase" pattern), which also removes the
// "same-size cards of icon plus heading plus text" default the design
// system's own craft floor flags. Reuses the existing landing.features.*
// i18n keys unchanged — this is a container/presentation change, not new
// copy.
const TABS = [
  { key: 'bilingual', titleKey: 'landing.features.bilingual.title', descKey: 'landing.features.bilingual.desc' },
  { key: 'cited', titleKey: 'landing.features.cited.title', descKey: 'landing.features.cited.desc' },
  { key: 'voice', titleKey: 'landing.features.voice.title', descKey: 'landing.features.voice.desc' },
  { key: 'warung', titleKey: 'landing.features.warung.title', descKey: 'landing.features.warung.desc' },
  { key: 'api', titleKey: 'landing.features.api.title', descKey: 'landing.features.api.desc' },
] as const;

type TabKey = (typeof TABS)[number]['key'];

interface LandingFeatureShowcaseProps {
  isDark?: boolean;
}

export function LandingFeatureShowcase({ isDark = true }: LandingFeatureShowcaseProps) {
  const { t } = useI18n();
  const [active, setActive] = useState<TabKey>('cited');

  const panelClass = isDark ? 'bg-[#0d0f14] border-white/10' : 'bg-[#161821] border-black/10';
  const tabActiveClass = isDark ? 'bg-white/10 text-white' : 'bg-white/10 text-white';
  const tabIdleClass = 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5';

  return (
    <div
      className={`grid grid-cols-1 lg:grid-cols-[minmax(0,280px)_1fr] gap-0 rounded-2xl border overflow-hidden ${panelClass}`}
    >
      {/* Tab list — vertical pills on desktop (Fixa/V7's pattern), a
          horizontal scroller on mobile since there's no room for a side
          rail under the mockup at narrow widths. */}
      <div className="flex lg:flex-col gap-1.5 overflow-x-auto lg:overflow-visible p-4 sm:p-5 lg:border-r border-white/10">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActive(tab.key)}
            className={`flex-shrink-0 text-left rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors locale-nowrap lg:locale-text-balance ${
              active === tab.key ? tabActiveClass : tabIdleClass
            }`}
          >
            {t(tab.titleKey)}
          </button>
        ))}
      </div>

      {/* Mockup panel — small representative visuals built from the app's
          own tokens/motifs (the CitationChip "stamp", nk-community gold,
          font-mono), not screenshots of real pages, so they can't drift out
          of sync with the product the way a static screenshot would. */}
      <div className="relative min-h-[280px] sm:min-h-[320px] p-6 sm:p-10 flex flex-col justify-center overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={active}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="flex flex-col gap-6"
          >
            <TabMockup tabKey={active} />
            <p className="text-sm text-zinc-400 leading-relaxed max-w-sm locale-text-balance">
              {t(TABS.find((tb) => tb.key === active)!.descKey)}
            </p>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function TabMockup({ tabKey }: { tabKey: TabKey }) {
  const { t } = useI18n();

  if (tabKey === 'bilingual') {
    return (
      <div className="flex items-center gap-2">
        {(['BM', 'EN', '中文'] as const).map((lbl, i) => (
          <span
            key={lbl}
            className={`rounded-full px-4 py-2 text-sm font-semibold locale-nowrap ${
              i === 0 ? 'bg-nk-official text-white' : 'bg-white/10 text-zinc-400'
            }`}
          >
            {lbl}
          </span>
        ))}
      </div>
    );
  }

  if (tabKey === 'cited') {
    // Same stamp motif as CitationChip.tsx's real citation chip (double
    // border, mono uppercase) — deliberately generic/unlabeled rather than
    // naming a specific agency, since this is illustrative UI chrome, not a
    // claim about a specific source.
    return (
      <div className="flex flex-col gap-3 max-w-xs">
        <span className="self-start inline-flex items-center rounded-md border-2 border-double border-nk-official/40 bg-nk-official/15 px-2.5 py-1 text-[11px] font-mono font-bold uppercase tracking-wide text-nk-official">
          {t('landing.features.cited.stamp')}
        </span>
        <div className="flex flex-col gap-1.5" aria-hidden>
          <div className="h-2 rounded-full bg-white/15 w-full" />
          <div className="h-2 rounded-full bg-white/15 w-4/5" />
          <div className="h-2 rounded-full bg-white/10 w-3/5" />
        </div>
      </div>
    );
  }

  if (tabKey === 'voice') {
    return (
      <div className="flex items-center gap-3">
        <span className="flex-shrink-0 flex items-center justify-center w-11 h-11 rounded-full bg-nk-official/15 text-nk-official">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden>
            <path d="M7 4a3 3 0 0 1 6 0v6a3 3 0 1 1-6 0V4Z" />
            <path d="M5.5 9.643a.75.75 0 0 0-1.5 0V10c0 3.06 2.29 5.585 5.25 5.954V17.5h-1.5a.75.75 0 0 0 0 1.5h4.5a.75.75 0 0 0 0-1.5h-1.5v-1.546A6.001 6.001 0 0 0 16 10v-.357a.75.75 0 0 0-1.5 0V10a4.5 4.5 0 0 1-9 0v-.357Z" />
          </svg>
        </span>
        <div className="flex items-end gap-1 h-8" aria-hidden>
          {[10, 22, 14, 28, 18, 24, 12].map((h, i) => (
            <span key={i} className="w-1.5 rounded-full bg-nk-official/50" style={{ height: `${h}px` }} />
          ))}
        </div>
      </div>
    );
  }

  if (tabKey === 'warung') {
    return (
      <div className="inline-flex items-center gap-2 rounded-full border-2 border-dashed border-nk-community/40 bg-nk-community/10 px-4 py-2">
        <span className="relative flex h-2 w-2 flex-shrink-0" aria-hidden>
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-nk-community opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-nk-community" />
        </span>
        <span className="text-sm font-semibold text-nk-community locale-nowrap">🍜 {t('nav.warung_watch')}</span>
      </div>
    );
  }

  // api
  return (
    <div className="rounded-lg border border-white/10 bg-black/30 px-4 py-3 font-mono text-xs text-zinc-400 max-w-xs overflow-x-auto">
      <div><span className="text-nk-official">POST</span> /api/v1/public/query</div>
      <div className="mt-1 text-zinc-600">{'{ "query": "...", "language": "bm" }'}</div>
    </div>
  );
}
