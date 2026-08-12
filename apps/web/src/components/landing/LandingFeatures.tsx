'use client';

import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

const FEATURE_KEYS = [
  { key: 'bilingual', titleKey: 'landing.features.bilingual.title', descKey: 'landing.features.bilingual.desc' },
  { key: 'cited', titleKey: 'landing.features.cited.title', descKey: 'landing.features.cited.desc' },
  { key: 'voice', titleKey: 'landing.features.voice.title', descKey: 'landing.features.voice.desc' },
  { key: 'warung', titleKey: 'landing.features.warung.title', descKey: 'landing.features.warung.desc' },
  { key: 'api', titleKey: 'landing.features.api.title', descKey: 'landing.features.api.desc' },
] as const;

const FEATURE_ICONS: Record<string, React.ReactNode> = {
  bilingual: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
      <path d="M4.913 2.658c2.075-.27 4.19-.408 6.337-.408 2.147 0 4.262.139 6.337.408 1.922.25 3.291 1.861 3.405 3.727a4.403 4.403 0 0 0-1.032-.211 50.89 50.89 0 0 0-8.42 0c-2.358.196-4.04 2.19-4.04 4.434v4.286a4.47 4.47 0 0 0 2.433 3.984L7.28 21.53A.75.75 0 0 1 6 21v-4.03a48.527 48.527 0 0 1-1.087-.128C2.905 16.58 1.5 14.833 1.5 12.862V6.638c0-1.97 1.405-3.718 3.413-3.979Z" />
      <path d="M15.75 7.5c-1.376 0-2.739.057-4.086.169C10.124 7.797 9 9.103 9 10.609v4.285c0 1.507 1.128 2.814 2.67 2.94 1.243.102 2.5.157 3.768.165l2.782 2.781a.75.75 0 0 0 1.28-.53v-2.39l.33-.026c1.542-.125 2.67-1.433 2.67-2.94v-4.286c0-1.505-1.125-2.811-2.664-2.94A49.392 49.392 0 0 0 15.75 7.5Z" />
    </svg>
  ),
  voice: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
      <path d="M8.25 4.5a3.75 3.75 0 1 1 7.5 0v8.25a3.75 3.75 0 1 1-7.5 0V4.5Z" />
      <path d="M6 10.5a.75.75 0 0 1 .75.75v1.5a5.25 5.25 0 1 0 10.5 0v-1.5a.75.75 0 0 1 1.5 0v1.5a6.751 6.751 0 0 1-6 6.709v2.291h3a.75.75 0 0 1 0 1.5h-7.5a.75.75 0 0 1 0-1.5h3v-2.291a6.751 6.751 0 0 1-6-6.709v-1.5A.75.75 0 0 1 6 10.5Z" />
    </svg>
  ),
  api: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
      <path fillRule="evenodd" d="M14.447 3.026a.75.75 0 0 1 .527.921l-4.5 16.5a.75.75 0 0 1-1.448-.394l4.5-16.5a.75.75 0 0 1 .921-.527ZM16.72 6.22a.75.75 0 0 1 1.06 0l5.25 5.25a.75.75 0 0 1 0 1.06l-5.25 5.25a.75.75 0 1 1-1.06-1.06L21.44 12l-4.72-4.72a.75.75 0 0 1 0-1.06Zm-9.44 0a.75.75 0 0 1 0 1.06L2.56 12l4.72 4.72a.75.75 0 0 1-1.06 1.06L.97 12.53a.75.75 0 0 1 0-1.06l5.25-5.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
    </svg>
  ),
};

interface LandingFeaturesProps {
  isDark?: boolean;
}

export function LandingFeatures({ isDark = true }: LandingFeaturesProps) {
  const { t } = useI18n();
  const cardClass = isDark
    ? 'bg-white/5 border-white/10 hover:border-white/20'
    : 'bg-white border-zinc-200 shadow-sm hover:shadow-md';
  const tileClass = isDark ? 'bg-nk-official/15 text-nk-official' : 'bg-nk-official/10 text-nk-official-dim';
  const titleClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const descClass = isDark ? 'text-zinc-400' : 'text-zinc-600';

  // flex-wrap + a fixed basis per breakpoint (instead of CSS grid) so a
  // partial last row centers itself rather than left-packing with an
  // empty gap where a 3rd/2nd tile would be — 5 cards in a 3-col grid
  // otherwise reads as "one tile missing" rather than "5 features".
  return (
    <div className="flex flex-wrap justify-center gap-4 sm:gap-6 max-w-4xl mx-auto w-full">
      {FEATURE_KEYS.map((f) => {
        const cardBasis = 'basis-full sm:basis-[calc(50%-0.75rem)] lg:basis-[calc(33.333%-1rem)]';

        if (f.key === 'cited') {
          // The stamp treatment — same visual language as the real citation
          // chips users see in chat (double border, mono uppercase label) —
          // is the one deliberate departure from the uniform icon-square
          // treatment every other card uses. This card IS the trust claim,
          // so it gets to look like the interaction pattern it's teasing
          // instead of blending in with "Voice Input".
          return (
            <motion.div
              key={f.key}
              whileHover={{ y: -4 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
              className={`flex flex-col gap-4 border-2 border-double rounded-2xl p-5 sm:p-6 transition-colors duration-200 ${cardBasis} ${
                isDark ? 'bg-nk-official/5 border-nk-official/40 hover:border-nk-official/60' : 'bg-nk-official/5 border-nk-official/30 hover:border-nk-official/50'
              }`}
            >
              <span
                className={`self-start inline-flex items-center rounded-md border-2 border-double px-2.5 py-1 text-[11px] font-mono font-bold uppercase tracking-wide ${
                  isDark ? 'bg-nk-official/15 text-nk-official border-nk-official/40' : 'bg-nk-official/10 text-nk-official-dim border-nk-official/30'
                }`}
              >
                {t('landing.features.cited.stamp')}
              </span>
              <h3 className={`font-semibold locale-nowrap ${titleClass}`}>{t(f.titleKey)}</h3>
              <p className={`text-sm leading-relaxed locale-text-balance ${descClass}`}>{t(f.descKey)}</p>
            </motion.div>
          );
        }

        if (f.key === 'warung') {
          // Gold accent + the same 🍜 teacup/noodle-bowl metaphor used in the
          // sidebar and landing spotlight — one icon per concept, everywhere
          // — so this card pre-teaches the blue/gold official-vs-community
          // distinction before a visitor ever reaches the sidebar.
          return (
            <motion.div
              key={f.key}
              whileHover={{ y: -4 }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
              className={`flex flex-col gap-4 border rounded-2xl p-5 sm:p-6 transition-colors duration-200 ${cardBasis} ${
                isDark ? 'bg-white/5 border-white/10 hover:border-white/20 border-l-4 border-l-nk-community' : 'bg-white border-zinc-200 shadow-sm hover:shadow-md border-l-4 border-l-nk-community'
              }`}
            >
              <span className={`inline-flex h-12 w-12 items-center justify-center rounded-xl text-2xl ${isDark ? 'bg-nk-community/15' : 'bg-nk-community/10'}`}>
                <span aria-hidden="true">🍜</span>
              </span>
              <h3 className={`font-semibold locale-nowrap ${titleClass}`}>{t(f.titleKey)}</h3>
              <p className={`text-sm leading-relaxed locale-text-balance ${descClass}`}>{t(f.descKey)}</p>
            </motion.div>
          );
        }

        return (
          <motion.div
            key={f.key}
            whileHover={{ y: -4 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            className={`flex flex-col gap-4 border rounded-2xl p-5 sm:p-6 transition-colors duration-200 ${cardBasis} ${cardClass}`}
          >
            <span className={`inline-flex h-12 w-12 items-center justify-center rounded-xl ${tileClass}`}>
              {FEATURE_ICONS[f.key]}
            </span>
            <h3 className={`font-semibold locale-nowrap ${titleClass}`}>{t(f.titleKey)}</h3>
            <p className={`text-sm leading-relaxed locale-text-balance ${descClass}`}>{t(f.descKey)}</p>
          </motion.div>
        );
      })}
    </div>
  );
}
