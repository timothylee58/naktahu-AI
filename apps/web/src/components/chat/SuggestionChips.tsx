'use client';

import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (query: string) => void;
  disabled?: boolean;
}

const spring = { duration: 0.28, ease: [0.16, 1, 0.3, 1] } as const;

export function SuggestionChips({ suggestions, onSelect, disabled }: SuggestionChipsProps) {
  const { t } = useI18n();

  if (suggestions.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...spring, delay: 0.2 }}
      className="flex flex-col gap-2 mt-2"
    >
      <span className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">{t('chat.suggestions_label')}</span>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((suggestion, index) => (
          <motion.button
            key={index}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ ...spring, delay: 0.3 + index * 0.1 }}
            onClick={() => onSelect(suggestion)}
            disabled={disabled}
            className="flex items-center gap-1.5 px-3 py-2 bg-nk-official/10 hover:bg-nk-official/20 text-nk-official-dim border border-nk-official/30 rounded-lg text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-left dark:bg-nk-official/10 dark:hover:bg-nk-official-dim/20 dark:text-nk-official dark:border-nk-official/30"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 16 16"
              fill="currentColor"
              className="w-3.5 h-3.5 flex-shrink-0"
            >
              <path
                fillRule="evenodd"
                d="M8 1a.75.75 0 0 1 .75.75v6.5a.75.75 0 0 1-1.5 0v-6.5A.75.75 0 0 1 8 1ZM4.11 3.05a.75.75 0 0 1 0 1.06L2.525 5.7a.75.75 0 0 1-1.06-1.06l1.585-1.585a.75.75 0 0 1 1.06 0Zm7.78 0a.75.75 0 0 1 1.06 0l1.585 1.585a.75.75 0 1 1-1.06 1.06L11.89 4.11a.75.75 0 0 1 0-1.06ZM8 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"
                clipRule="evenodd"
              />
            </svg>
            <span className="line-clamp-2">{suggestion}</span>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}
