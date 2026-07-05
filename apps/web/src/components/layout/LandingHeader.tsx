'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import { AuthButton } from '@/components/auth/AuthButton';
import { LangToggle } from '@/components/LangToggle';
import { ThemeToggle } from '@/components/ThemeToggle';
import { SiteNavLinks } from '@/components/layout/SiteNavLinks';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

export function LandingHeader() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const isDark = theme === 'dark';

  const shellClass = isDark
    ? 'border-white/10 bg-[#0A0F1E]/90 text-white'
    : 'border-zinc-200 bg-white/90 text-zinc-900';
  const menuBtnClass = isDark
    ? 'text-zinc-400 hover:bg-white/10 hover:text-zinc-200'
    : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800';

  return (
    <header className={`sticky top-0 z-30 border-b backdrop-blur-md ${shellClass}`}>
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        <Link href="/" className="font-bold text-base tracking-tight locale-nowrap flex-shrink-0">
          NakTahu
        </Link>

        <div className="hidden md:flex items-center gap-1">
          <SiteNavLinks
            variant={isDark ? 'dark' : 'light'}
            layout="horizontal"
            hideHome
          />
        </div>

        <div className="hidden md:flex items-center gap-2 flex-shrink-0">
          <ThemeToggle variant={isDark ? 'dark' : 'light'} />
          <LangToggle variant={isDark ? 'dark' : 'light'} />
          <AuthButton variant={isDark ? 'dark' : 'light'} layout="compact" />
        </div>

        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label={t('header.menu')}
          className={`md:hidden p-2 rounded-lg transition-colors ${menuBtnClass}`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            {menuOpen ? (
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            ) : (
              <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
            )}
          </svg>
        </button>
      </div>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className={`md:hidden border-t overflow-hidden ${isDark ? 'border-white/10 bg-[#0A0F1E]' : 'border-zinc-200 bg-white'}`}
          >
            <div className="px-4 py-4 flex flex-col gap-4">
              <SiteNavLinks
                variant={isDark ? 'dark' : 'light'}
                layout="vertical"
                showChatCta
                hideHome
                excludeHrefs={LANDING_NAV_OMIT}
                onNavigate={() => setMenuOpen(false)}
              />
              <div className="flex flex-col gap-2 pt-2 border-t border-inherit">
                <ThemeToggle variant={isDark ? 'dark' : 'light'} layout="sidebar" />
                <LangToggle variant={isDark ? 'dark' : 'light'} layout="sidebar" />
                <AuthButton variant={isDark ? 'dark' : 'light'} layout="sidebar" />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
