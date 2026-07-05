'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { AuthErrorBanner } from '@/components/auth/AuthErrorBanner';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { TypewriterQueryWrapper } from './TypewriterQueryWrapper';
import { LandingFeatures } from './LandingFeatures';
import { useI18n } from '@/lib/i18n';
import { pickRandomTaglineKey } from '@/lib/landing-taglines';
import { useTheme } from '@/lib/theme';

const DOMAINS = [
  { key: 'tax' },
  { key: 'epf' },
  { key: 'business' },
  { key: 'education' },
  { key: 'health' },
  { key: 'immigration' },
] as const;

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: 'easeOut' as const },
  }),
};

export function LandingClient() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const [taglineKey] = useState(() => pickRandomTaglineKey());
  const tagline = t(taglineKey);
  const isDark = theme === 'dark';

  const pageClass = isDark
    ? 'min-h-screen bg-[#0A0F1E] text-white'
    : 'min-h-screen bg-zinc-50 text-zinc-900';
  const borderClass = isDark ? 'border-white/10' : 'border-zinc-200';
  const mutedText = isDark ? 'text-zinc-400' : 'text-zinc-600';
  const sectionTitle = isDark ? 'text-zinc-200' : 'text-zinc-800';
  const searchBoxClass = isDark
    ? 'bg-white/5 border-white/10'
    : 'bg-white border-zinc-200 shadow-sm';
  const domainPillClass = isDark
    ? 'border-[#2563EB]/40 text-[#2563EB] bg-[#2563EB]/10'
    : 'border-blue-200 text-blue-700 bg-blue-50';
  const footerText = isDark ? 'text-zinc-500' : 'text-zinc-500';
  const footerTitle = isDark ? 'text-zinc-300' : 'text-zinc-700';

  return (
    <div className={`flex flex-col font-sans ${pageClass}`}>
      <LandingHeader />
      <AuthErrorBanner />

      <section className="flex flex-col items-center justify-center flex-1 text-center px-4 sm:px-6 py-16 sm:py-24 gap-6 sm:gap-8 max-w-6xl mx-auto w-full">
        <motion.div
          custom={0}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className="inline-flex items-center gap-2 text-xs font-semibold tracking-widest text-[#2563EB] uppercase border border-[#2563EB]/30 rounded-full px-4 py-1.5 locale-nowrap"
        >
          🇲🇾 {t('landing.badge')}
        </motion.div>

        <motion.h1
          custom={1}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className="text-3xl sm:text-5xl lg:text-6xl font-bold leading-tight max-w-3xl tracking-tight locale-text-balance"
        >
          {(() => {
            const headline = t('landing.hero.headline');
            const highlight = t('landing.hero.headline.highlight');
            const idx = headline.indexOf(highlight);
            if (idx === -1) return headline;
            return (
              <>
                {headline.slice(0, idx)}
                <span className="text-[#2563EB]">{highlight}</span>
                {headline.slice(idx + highlight.length)}
              </>
            );
          })()}
        </motion.h1>

        <motion.p
          custom={2}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className={`text-base sm:text-lg max-w-xl leading-relaxed locale-text-balance ${mutedText}`}
        >
          {tagline}
        </motion.p>

        <motion.div
          custom={3}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className={`w-full max-w-xl border rounded-2xl px-4 sm:px-5 py-3.5 sm:py-4 flex items-center gap-3 ${searchBoxClass}`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`w-5 h-5 flex-shrink-0 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}
          >
            <path
              fillRule="evenodd"
              d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z"
              clipRule="evenodd"
            />
          </svg>
          <TypewriterQueryWrapper isDark={isDark} />
        </motion.div>

        <motion.div custom={4} variants={fadeUp} initial="hidden" animate="show">
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 bg-[#2563EB] hover:bg-blue-500 transition-colors text-white font-semibold px-6 sm:px-8 py-3 sm:py-3.5 rounded-full text-sm sm:text-base shadow-lg shadow-blue-900/30 locale-nowrap"
          >
            {t('landing.hero.cta')}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-5 h-5"
            >
              <path
                fillRule="evenodd"
                d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10Z"
                clipRule="evenodd"
              />
            </svg>
          </Link>
        </motion.div>
      </section>

      <motion.section
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className={`px-4 sm:px-6 py-16 sm:py-20 border-t ${borderClass} max-w-6xl mx-auto w-full`}
      >
        <h2 className={`text-center text-xl sm:text-2xl font-bold mb-10 sm:mb-12 locale-text-balance ${sectionTitle}`}>
          {t('landing.features.title')}
        </h2>
        <LandingFeatures isDark={isDark} />
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.5 }}
        className={`px-4 sm:px-6 py-14 sm:py-16 border-t ${borderClass} flex flex-col items-center gap-6 max-w-6xl mx-auto w-full`}
      >
        <h2 className={`text-xl sm:text-2xl font-bold locale-text-balance ${sectionTitle}`}>
          {t('landing.domains.title')}
        </h2>
        <div className="flex flex-wrap justify-center gap-2 sm:gap-3 max-w-2xl">
          {DOMAINS.map((d, i) => (
            <motion.span
              key={d.key}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.06, duration: 0.3 }}
              className={`border rounded-full px-3 sm:px-4 py-1.5 text-sm font-medium locale-nowrap ${domainPillClass}`}
            >
              {t(`domain.${d.key}`)}
            </motion.span>
          ))}
        </div>
      </motion.section>

      <footer className={`border-t ${borderClass} px-4 sm:px-6 py-8 sm:py-10 max-w-6xl mx-auto w-full flex flex-col sm:flex-row items-center justify-between gap-4 text-sm ${footerText}`}>
        <div className="flex flex-col gap-1 text-center sm:text-left">
          <span className={`font-semibold locale-nowrap ${footerTitle}`}>NakTahu AI</span>
          <span className="locale-text-balance">{tagline}</span>
        </div>
        <div className="flex flex-col items-center sm:items-end gap-1 text-center sm:text-right">
          <div className="flex items-center gap-3">
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className={`transition-colors locale-nowrap ${isDark ? 'hover:text-white' : 'hover:text-zinc-900'}`}
            >
              {t('landing.footer.github')} ↗
            </a>
            <Link
              href="/privacy"
              className={`transition-colors locale-nowrap ${isDark ? 'hover:text-white' : 'hover:text-zinc-900'}`}
            >
              {t('footer.privacy')}
            </Link>
          </div>
          <span className="text-xs max-w-xs locale-text-balance">
            {t('landing.footer.disclaimer')}
          </span>
        </div>
      </footer>
    </div>
  );
}
