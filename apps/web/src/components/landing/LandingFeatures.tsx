'use client';

import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

const FEATURE_KEYS = [
  { titleKey: 'landing.features.bilingual.title', descKey: 'landing.features.bilingual.desc' },
  { titleKey: 'landing.features.cited.title', descKey: 'landing.features.cited.desc' },
  { titleKey: 'landing.features.voice.title', descKey: 'landing.features.voice.desc' },
  { titleKey: 'landing.features.warung.title', descKey: 'landing.features.warung.desc' },
  { titleKey: 'landing.features.api.title', descKey: 'landing.features.api.desc' },
] as const;

const FEATURE_ICONS = [
  (
    <svg key="bilingual" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
      <path d="M4.913 2.658c2.075-.27 4.19-.408 6.337-.408 2.147 0 4.262.139 6.337.408 1.922.25 3.291 1.861 3.405 3.727a4.403 4.403 0 0 0-1.032-.211 50.89 50.89 0 0 0-8.42 0c-2.358.196-4.04 2.19-4.04 4.434v4.286a4.47 4.47 0 0 0 2.433 3.984L7.28 21.53A.75.75 0 0 1 6 21v-4.03a48.527 48.527 0 0 1-1.087-.128C2.905 16.58 1.5 14.833 1.5 12.862V6.638c0-1.97 1.405-3.718 3.413-3.979Z" />
      <path d="M15.75 7.5c-1.376 0-2.739.057-4.086.169C10.124 7.797 9 9.103 9 10.609v4.285c0 1.507 1.128 2.814 2.67 2.94 1.243.102 2.5.157 3.768.165l2.782 2.781a.75.75 0 0 0 1.28-.53v-2.39l.33-.026c1.542-.125 2.67-1.433 2.67-2.94v-4.286c0-1.505-1.125-2.811-2.664-2.94A49.392 49.392 0 0 0 15.75 7.5Z" />
    </svg>
  ),
  (
    <svg key="cited" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
      <path fillRule="evenodd" d="M15.75 2.25H21a.75.75 0 0 1 .75.75v5.25a.75.75 0 0 1-1.5 0V4.81L8.03 17.03a.75.75 0 0 1-1.06-1.06L19.19 3.75h-3.44a.75.75 0 0 1 0-1.5Zm-10.5 4.5a1.5 1.5 0 0 0-1.5 1.5v10.5a1.5 1.5 0 0 0 1.5 1.5h10.5a1.5 1.5 0 0 0 1.5-1.5V10.5a.75.75 0 0 1 1.5 0v8.25a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3V8.25a3 3 0 0 1 3-3h8.25a.75.75 0 0 1 0 1.5H5.25Z" clipRule="evenodd" />
    </svg>
  ),
  (
    <svg key="voice" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
      <path d="M8.25 4.5a3.75 3.75 0 1 1 7.5 0v8.25a3.75 3.75 0 1 1-7.5 0V4.5Z" />
      <path d="M6 10.5a.75.75 0 0 1 .75.75v1.5a5.25 5.25 0 1 0 10.5 0v-1.5a.75.75 0 0 1 1.5 0v1.5a6.751 6.751 0 0 1-6 6.709v2.291h3a.75.75 0 0 1 0 1.5h-7.5a.75.75 0 0 1 0-1.5h3v-2.291a6.751 6.751 0 0 1-6-6.709v-1.5A.75.75 0 0 1 6 10.5Z" />
    </svg>
  ),
  (
    <svg key="warung" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
      <path fillRule="evenodd" d="M12 1.5a.75.75 0 0 1 .75.75V4.5a.75.75 0 0 1-1.5 0V2.25A.75.75 0 0 1 12 1.5ZM5.636 4.136a.75.75 0 0 1 1.06 0l1.592 1.591a.75.75 0 0 1-1.061 1.06l-1.591-1.59a.75.75 0 0 1 0-1.061Zm12.728 0a.75.75 0 0 1 0 1.06l-1.591 1.592a.75.75 0 0 1-1.06-1.061l1.59-1.591a.75.75 0 0 1 1.061 0ZM3 10.5a.75.75 0 0 1 .75-.75H6a.75.75 0 0 1 0 1.5H3.75A.75.75 0 0 1 3 10.5Zm14.25 0a.75.75 0 0 1 .75-.75h2.25a.75.75 0 0 1 0 1.5H18a.75.75 0 0 1-.75-.75ZM12 18a.75.75 0 0 1 .75.75V21a.75.75 0 0 1-1.5 0v-2.25A.75.75 0 0 1 12 18ZM4.5 21a3 3 0 0 1-3-3v-.75A2.25 2.25 0 0 1 3.75 15h16.5a2.25 2.25 0 0 1 2.25 2.25V18a3 3 0 0 1-3 3h-15Zm.75-11.25a6.75 6.75 0 0 1 13.5 0v3H5.25v-3Z" clipRule="evenodd" />
    </svg>
  ),
  (
    <svg key="api" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7">
      <path fillRule="evenodd" d="M14.447 3.026a.75.75 0 0 1 .527.921l-4.5 16.5a.75.75 0 0 1-1.448-.394l4.5-16.5a.75.75 0 0 1 .921-.527ZM16.72 6.22a.75.75 0 0 1 1.06 0l5.25 5.25a.75.75 0 0 1 0 1.06l-5.25 5.25a.75.75 0 1 1-1.06-1.06L21.44 12l-4.72-4.72a.75.75 0 0 1 0-1.06Zm-9.44 0a.75.75 0 0 1 0 1.06L2.56 12l4.72 4.72a.75.75 0 0 1-1.06 1.06L.97 12.53a.75.75 0 0 1 0-1.06l5.25-5.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
    </svg>
  ),
];

interface LandingFeaturesProps {
  isDark?: boolean;
}

export function LandingFeatures({ isDark = true }: LandingFeaturesProps) {
  const { t } = useI18n();
  const cardClass = isDark
    ? 'bg-white/5 border-white/10 hover:border-white/20'
    : 'bg-white border-zinc-200 shadow-sm hover:shadow-md';
  const tileClass = isDark ? 'bg-blue-500/15 text-blue-300' : 'bg-blue-50 text-blue-600';
  const titleClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const descClass = isDark ? 'text-zinc-400' : 'text-zinc-600';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 max-w-4xl mx-auto w-full">
      {FEATURE_KEYS.map((f, i) => (
        <motion.div
          key={f.titleKey}
          whileHover={{ y: -4 }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
          className={`flex flex-col gap-4 border rounded-2xl p-5 sm:p-6 transition-colors duration-200 ${cardClass}`}
        >
          <span className={`inline-flex h-12 w-12 items-center justify-center rounded-xl ${tileClass}`}>
            {FEATURE_ICONS[i]}
          </span>
          <h3 className={`font-semibold locale-nowrap ${titleClass}`}>{t(f.titleKey)}</h3>
          <p className={`text-sm leading-relaxed locale-text-balance ${descClass}`}>{t(f.descKey)}</p>
        </motion.div>
      ))}
    </div>
  );
}
