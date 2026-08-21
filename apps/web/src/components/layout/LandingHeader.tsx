'use client';

import { useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import { AuthButton } from '@/components/auth/AuthButton';
import { NakTahuWordmark } from '@/components/logo/NakTahuWordmark';
import { LangToggle } from '@/components/LangToggle';
import { ThemeToggle } from '@/components/ThemeToggle';
import { SiteNavLinks } from '@/components/layout/SiteNavLinks';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

const LANDING_NAV_OMIT = ['/agents'] as const;

interface LandingHeaderProps {
  /** True mid-transition into /chat — morphs the header's own box from a
   * full top bar into the same left-sidebar rect AppSidebar occupies once
   * /chat actually mounts (see LandingClient's "Mula Bertanya" handler).
   * Defaults to false, which renders identically to before this prop
   * existed — /about and /faq (the other two LandingHeader consumers)
   * never pass it and are byte-for-byte unaffected. */
  collapsing?: boolean;
}

export function LandingHeader({ collapsing = false }: LandingHeaderProps) {
  const { t } = useI18n();
  const { theme } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const isDark = theme === 'dark';

  const shellClass = isDark
    ? 'border-white/10 bg-[#12151C]/90 text-white'
    : 'border-zinc-200 bg-white/90 text-zinc-900';
  const menuBtnClass = isDark
    ? 'text-zinc-400 hover:bg-white/10 hover:text-zinc-200'
    : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800';

  return (
    <motion.header
      // Boolean, not the `layout` shorthand (always-true): false for every
      // /about and /faq render (they never pass `collapsing`) means no FLIP
      // tracking at all there — identical behaviour to a plain <header>,
      // preserving the "byte-for-byte unaffected" contract on those two
      // consumers even though this file now always renders a motion.header.
      layout={collapsing}
      transition={{ type: 'spring', stiffness: 260, damping: 30 }}
      className={`z-30 backdrop-blur-md ${
        collapsing
          ? 'fixed inset-y-0 left-0 border-r w-72 h-full overflow-hidden'
          : 'sticky top-0 border-b w-full'
      } ${shellClass}`}
    >
      <motion.div
        layout={collapsing}
        className={`max-w-6xl mx-auto px-4 sm:px-6 gap-4 ${
          collapsing ? 'flex flex-col items-start pt-5 h-full' : 'h-14 flex items-center justify-between'
        }`}
      >
        <Link
          href="/"
          className="inline-flex items-center text-lg flex-shrink-0"
          // Collapsing into a sidebar shape is a one-way trip to /chat —
          // the logo link shouldn't compete with that mid-transition.
          tabIndex={collapsing ? -1 : undefined}
          aria-hidden={collapsing || undefined}
        >
          <NakTahuWordmark markSize={26} />
        </Link>

        {/* Nav/toggles fade out during the morph rather than trying to
            reflow horizontal nav into a vertical list mid-flight — this is
            a shape transition to the sidebar's rect, not a full content
            swap (AppSidebar itself mounts for real once /chat lands). */}
        <motion.div
          animate={collapsing ? { opacity: 0 } : { opacity: 1 }}
          transition={{ duration: 0.15 }}
          className={collapsing ? 'pointer-events-none' : 'contents'}
        >
          <div className="hidden md:flex items-center gap-1">
            <SiteNavLinks
              variant={isDark ? 'dark' : 'light'}
              layout="horizontal"
              hideHome
              excludeHrefs={LANDING_NAV_OMIT}
            />
          </div>

          <div className="hidden md:flex items-center gap-2 flex-shrink-0">
            <ThemeToggle variant={isDark ? 'dark' : 'light'} />
            <LangToggle variant={isDark ? 'dark' : 'light'} />
            <AuthButton variant={isDark ? 'dark' : 'light'} layout="compact" />
          </div>
        </motion.div>

        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          aria-label={t('header.menu')}
          tabIndex={collapsing ? -1 : undefined}
          aria-hidden={collapsing || undefined}
          className={`md:hidden p-2 rounded-lg transition-colors ${collapsing ? 'opacity-0 pointer-events-none' : ''} ${menuBtnClass}`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            {menuOpen ? (
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            ) : (
              <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
            )}
          </svg>
        </button>
      </motion.div>

      <AnimatePresence>
        {menuOpen && !collapsing && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className={`md:hidden border-t overflow-hidden ${isDark ? 'border-white/10 bg-[#12151C]' : 'border-zinc-200 bg-white'}`}
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
    </motion.header>
  );
}
