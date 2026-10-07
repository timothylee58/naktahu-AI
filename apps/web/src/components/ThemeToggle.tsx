'use client';

import { motion } from 'framer-motion';
import { Moon, Sun } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

interface ThemeToggleProps {
  variant?: 'dark' | 'light';
  layout?: 'inline' | 'sidebar';
}

export function ThemeToggle({ variant = 'dark', layout = 'inline' }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  const { t } = useI18n();
  const isDarkUi = variant === 'dark';
  const isSidebar = layout === 'sidebar';

  const buttonClass = isSidebar
    ? isDarkUi
      ? 'w-full justify-between bg-white/5 hover:bg-white/10 border-white/20 text-zinc-200 rounded-xl px-4 py-2.5'
      : 'w-full justify-between bg-white hover:bg-zinc-50 border-zinc-200 text-zinc-700 rounded-xl px-4 py-2.5'
    : isDarkUi
      ? 'bg-white/5 hover:bg-white/10 border-white/20 text-zinc-200 rounded-full px-3 py-1.5'
      : 'bg-zinc-100 hover:bg-zinc-200 border-zinc-200 text-zinc-700 rounded-full px-3 py-1.5';

  return (
    <motion.button
      type="button"
      onClick={toggleTheme}
      whileTap={{ scale: 0.95 }}
      aria-label={theme === 'dark' ? t('theme.switch_light') : t('theme.switch_dark')}
      className={`flex items-center gap-2 border text-xs font-semibold transition-colors locale-nowrap ${buttonClass}`}
    >
      {theme === 'dark' ? (
        <Moon size={18} strokeWidth={1.75} className="flex-shrink-0" />
      ) : (
        <Sun size={18} strokeWidth={1.75} className="flex-shrink-0" />
      )}
      {isSidebar && (
        <span className="flex-1 text-left text-sm">
          {theme === 'dark' ? t('theme.dark') : t('theme.light')}
        </span>
      )}
    </motion.button>
  );
}
