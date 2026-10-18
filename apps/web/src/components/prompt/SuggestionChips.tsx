'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { CATEGORIES, type CategoryId } from '@/lib/categories';

interface SuggestionChipsProps {
  category: CategoryId;
  onSelect: (text: string) => void;
  disabled?: boolean;
}

export function SuggestionChips({ category, onSelect, disabled }: SuggestionChipsProps) {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion();
  const chips = CATEGORIES.find((c) => c.id === category)?.chips ?? [];

  return (
    // min-h reserves the row so switching tabs never shifts the page.
    <motion.div
      key={category}
      initial={reduceMotion ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.14 }}
      className="flex min-h-11 flex-wrap gap-2 sm:justify-center"
    >
      {chips.map((key) => (
        <button
          key={key}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(t(key))}
          className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-[var(--nk-chip-border)] px-4 text-sm font-medium text-nk-official-text transition-colors hover:bg-[var(--nk-fill-official)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official disabled:opacity-50 sm:px-[18px]"
        >
          {t(key)}
          <ArrowRight aria-hidden className="h-3.5 w-3.5" />
        </button>
      ))}
    </motion.div>
  );
}
