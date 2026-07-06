'use client';

import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { FEATURE_ICONS } from './FeatureIcons';

const FEATURE_KEYS = [
  { titleKey: 'landing.features.bilingual.title', descKey: 'landing.features.bilingual.desc' },
  { titleKey: 'landing.features.cited.title', descKey: 'landing.features.cited.desc' },
  { titleKey: 'landing.features.voice.title', descKey: 'landing.features.voice.desc' },
] as const;

interface LandingFeaturesProps {
  isDark?: boolean;
}

export function LandingFeatures({ isDark = true }: LandingFeaturesProps) {
  const { t } = useI18n();
  const cardClass = isDark
    ? 'bg-white/5 border-white/10'
    : 'bg-white border-zinc-200 shadow-sm';
  const titleClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const descClass = isDark ? 'text-zinc-400' : 'text-zinc-600';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 max-w-4xl mx-auto w-full">
      {FEATURE_KEYS.map((f, i) => {
        const Icon = FEATURE_ICONS[i];
        return (
          <motion.div
            key={f.titleKey}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-60px' }}
            transition={{ delay: i * 0.08, duration: 0.45, ease: 'easeOut' }}
            whileHover={{ y: -4 }}
            className={`flex flex-col gap-4 border rounded-2xl p-5 sm:p-6 ${cardClass}`}
          >
            <Icon />
            <h3 className={`font-semibold locale-nowrap ${titleClass}`}>{t(f.titleKey)}</h3>
            <p className={`text-sm leading-relaxed locale-text-balance ${descClass}`}>{t(f.descKey)}</p>
          </motion.div>
        );
      })}
    </div>
  );
}
