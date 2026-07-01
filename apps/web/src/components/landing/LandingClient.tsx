'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { AuthButton } from '@/components/auth/AuthButton';
import { AuthErrorBanner } from '@/components/auth/AuthErrorBanner';
import { LangToggle } from '@/components/LangToggle';
import { TypewriterQueryWrapper } from './TypewriterQueryWrapper';
import { LandingFeatures } from './LandingFeatures';
import { useI18n } from '@/lib/i18n';

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

  return (
    <div className="flex flex-col min-h-screen bg-[#0A0F1E] text-white font-sans">
      {/* Nav */}
      <motion.nav
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex items-center justify-between px-6 py-4 border-b border-white/10"
      >
        <span className="text-lg font-bold tracking-tight">NakTahu</span>
        <div className="flex items-center gap-3">
          <LangToggle />
          <AuthButton variant="dark" />
        </div>
      </motion.nav>

      <AuthErrorBanner />

      {/* Hero */}
      <section className="flex flex-col items-center justify-center flex-1 text-center px-6 py-24 gap-8">
        <motion.div
          custom={0}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className="inline-flex items-center gap-2 text-xs font-semibold tracking-widest text-[#2563EB] uppercase border border-[#2563EB]/30 rounded-full px-4 py-1.5"
        >
          🇲🇾 {t('landing.badge')}
        </motion.div>

        <motion.h1
          custom={1}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className="text-4xl sm:text-6xl font-bold leading-tight max-w-3xl tracking-tight"
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
          className="text-lg text-zinc-400 max-w-xl leading-relaxed"
        >
          {t('landing.hero.subtext')}
        </motion.p>

        {/* Animated search bar */}
        <motion.div
          custom={3}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className="w-full max-w-xl bg-white/5 border border-white/10 rounded-2xl px-5 py-4 flex items-center gap-3"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5 text-zinc-500 flex-shrink-0"
          >
            <path
              fillRule="evenodd"
              d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z"
              clipRule="evenodd"
            />
          </svg>
          <TypewriterQueryWrapper />
        </motion.div>

        <motion.div custom={4} variants={fadeUp} initial="hidden" animate="show">
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 bg-[#2563EB] hover:bg-blue-500 transition-colors text-white font-semibold px-8 py-3.5 rounded-full text-base shadow-lg shadow-blue-900/40"
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

      {/* Features */}
      <motion.section
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className="px-6 py-20 border-t border-white/10"
      >
        <h2 className="text-center text-2xl font-bold mb-12 text-zinc-200">
          {t('landing.features.title')}
        </h2>
        <LandingFeatures />
      </motion.section>

      {/* Domains */}
      <motion.section
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.5 }}
        className="px-6 py-16 border-t border-white/10 flex flex-col items-center gap-6"
      >
        <h2 className="text-2xl font-bold text-zinc-200">{t('landing.domains.title')}</h2>
        <div className="flex flex-wrap justify-center gap-3 max-w-2xl">
          {DOMAINS.map((d, i) => (
            <motion.span
              key={d.key}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.06, duration: 0.3 }}
              className="border border-[#2563EB]/40 text-[#2563EB] rounded-full px-4 py-1.5 text-sm font-medium bg-[#2563EB]/10"
            >
              {t(`domain.${d.key}`)}
            </motion.span>
          ))}
        </div>
      </motion.section>

      {/* Footer */}
      <footer className="border-t border-white/10 px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-zinc-500">
        <div className="flex flex-col gap-1">
          <span className="font-semibold text-zinc-300">NakTahu AI</span>
          <span>{t('landing.footer.tagline')}</span>
        </div>
        <div className="flex flex-col items-end gap-1 text-right">
          <div className="flex items-center gap-3">
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-white transition-colors"
            >
              {t('landing.footer.github')} ↗
            </a>
            <Link href="/privacy" className="hover:text-white transition-colors">
              {t('footer.privacy')}
            </Link>
          </div>
          <span className="text-xs max-w-xs text-right">
            {t('landing.footer.disclaimer')}
          </span>
        </div>
      </footer>
    </div>
  );
}
