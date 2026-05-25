'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import type { UILocale } from '@/lib/types';

const CYCLE: UILocale[] = ['en', 'ms', 'zh'];
const LABELS: Record<UILocale, string> = { en: 'EN', ms: 'BM', zh: '中文' };

export function LangToggle() {
  const { locale, setLocale } = useI18n();

  const next = () => {
    const idx = CYCLE.indexOf(locale);
    setLocale(CYCLE[(idx + 1) % CYCLE.length]);
  };

  return (
    <motion.button
      onClick={next}
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.94 }}
      className="relative w-14 h-8 flex items-center justify-center rounded-full border border-white/20 bg-white/5 hover:bg-white/10 transition-colors overflow-hidden"
      aria-label="Switch language"
    >
      <AnimatePresence mode="wait">
        <motion.span
          key={locale}
          initial={{ y: 8, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -8, opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="text-xs font-bold text-zinc-200 absolute"
        >
          {LABELS[locale]}
        </motion.span>
      </AnimatePresence>
    </motion.button>
  );
}
