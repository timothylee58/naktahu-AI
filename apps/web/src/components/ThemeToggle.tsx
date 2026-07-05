'use client';

import { motion } from 'framer-motion';
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
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 flex-shrink-0">
          <path d="M10 2a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 2ZM5.05 4.05a.75.75 0 0 1 1.06 0l1.062 1.06a.75.75 0 1 1-1.061 1.062L5.05 5.111a.75.75 0 0 1 0-1.06Zm9.9 0a.75.75 0 0 1 0 1.061l-1.06 1.061a.75.75 0 0 1-1.062-1.06l1.061-1.062a.75.75 0 0 1 1.061 0ZM3 8a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5A.75.75 0 0 1 3 8Zm11 0a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5A.75.75 0 0 1 14 8Zm-6.828 2.828a3 3 0 1 0 5.656 0 3 3 0 0 0-5.656 0ZM14 16a.75.75 0 0 1-.75.75h-6.5a.75.75 0 0 1 0-1.5h6.5A.75.75 0 0 1 14 16Zm-2.5-3.5a.75.75 0 0 0-3 0V14a.75.75 0 0 0 3 0v-1.5Z" />
        </svg>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 flex-shrink-0">
          <path fillRule="evenodd" d="M7.455 2.004a.75.75 0 0 1 .26.77 7 7 0 0 0 9.958 9.958.75.75 0 0 1 1.067.853A8.25 8.25 0 1 1 6.588 2.088a.75.75 0 0 1 .867-.084Z" clipRule="evenodd" />
        </svg>
      )}
      {isSidebar && (
        <span className="flex-1 text-left text-sm">
          {theme === 'dark' ? t('theme.dark') : t('theme.light')}
        </span>
      )}
    </motion.button>
  );
}
