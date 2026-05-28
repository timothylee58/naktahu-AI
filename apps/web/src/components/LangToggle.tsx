'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import type { UILocale } from '@/lib/types';

const CYCLE: UILocale[] = ['ms', 'en', 'zh'];
const LABELS: Record<UILocale, string> = { en: 'EN', ms: 'BM', zh: '中文' };

interface LangToggleProps {
  /** 'dark' = landing page glass style; 'light' = chat header style */
  variant?: 'dark' | 'light';
}

export function LangToggle({ variant = 'dark' }: LangToggleProps) {
  const { locale, setLocale } = useI18n();

  const next = () => {
    const idx = CYCLE.indexOf(locale);
    setLocale(CYCLE[(idx + 1) % CYCLE.length]);
  };

  const base = variant === 'light'
    ? 'bg-zinc-100 hover:bg-zinc-200 border-zinc-200'
    : 'bg-white/5 hover:bg-white/10 border-white/20';

  const textClass = variant === 'light' ? 'text-zinc-700' : 'text-zinc-200';

  return (
    <motion.button
      onClick={next}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      className={`relative flex items-center justify-center rounded-full border px-3 py-1.5 min-w-[3.5rem] h-8 transition-colors overflow-hidden ${base}`}
      aria-label="Switch language"
    >
      <AnimatePresence mode="wait">
        <motion.span
          key={locale}
          initial={{ y: 8, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -8, opacity: 0 }}
          transition={{ duration: 0.18 }}
          className={`text-xs font-bold absolute ${textClass}`}
        >
          {LABELS[locale]}
        </motion.span>
      </AnimatePresence>
    </motion.button>
  );
}
