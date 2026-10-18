'use client';

import { useEffect, useState, type MouseEvent as ReactMouseEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion, useReducedMotion } from 'framer-motion';
import { Callout, CalloutContent } from '@govtechmy/myds-react/callout';
import { Tag } from '@govtechmy/myds-react/tag';
import { AuthErrorBanner } from '@/components/auth/AuthErrorBanner';
import { PageLoadingScreen } from '@/components/ui/PageLoadingScreen';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { HomeHero } from '@/components/home/HomeHero';
import { LandingFeatureShowcase } from './LandingFeatureShowcase';
import { AgencyTrustGrid } from './AgencyTrustGrid';
import { PostcodePersonalizer } from './PostcodePersonalizer';
import { AgentSpotlight } from './AgentSpotlight';
import { ComparisonSection } from './ComparisonSection';
import { InteractiveAnswerPreview } from './InteractiveAnswerPreview';
import { useI18n } from '@/lib/i18n';
import {
  LANDING_TAGLINE_KEYS,
  pickRandomTaglineKey,
  type LandingTaglineKey,
} from '@/lib/landing-taglines';
import { useTheme } from '@/lib/theme';

// How long the header-morph + content fade plays before the actual route
// change fires — must match LandingHeader's spring feel closely enough
// that the router.push doesn't cut the animation off mid-flight, but not
// so long that the CTA feels laggy.
const CHAT_MORPH_MS = 420;

// Lighter beat than CHAT_MORPH_MS: this path has no header→sidebar shape
// morph to wait out (that treatment stays specific to the hero's own
// "Mula Bertanya" CTA, since only /chat has a real sidebar shape to morph
// into) — just enough time for the loading screen to read as intentional
// before the route actually changes underneath it.
const NAV_TRANSITION_MS = 380;

// Full domain badge list shown further down the page ("Knowledge Domains")
// — static, not clickable, distinct from the interactive hero chips above.
const ALL_DOMAINS = [
  { key: 'tax' },
  { key: 'epf' },
  { key: 'business' },
  { key: 'education' },
  { key: 'health' },
  { key: 'immigration' },
] as const;

export function LandingClient() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const router = useRouter();
  // Start from a stable key so SSR and the first client render match, then pick
  // a random tagline after mount. Calling Math.random() in the initial render
  // (server vs client) caused a hydration mismatch (React #418).
  const [taglineKey, setTaglineKey] = useState<LandingTaglineKey>(LANDING_TAGLINE_KEYS[0]);
  useEffect(() => {
    setTaglineKey(pickRandomTaglineKey());
  }, []);
  const tagline = t(taglineKey);
  const isDark = theme === 'dark';

  const reduceMotion = useReducedMotion();

  // ── Header → sidebar chat-morph. reduceMotion skips straight to
  // navigation — a shape-morphing header is exactly the kind of large
  // moving-object transition apple-design's reduced-motion guidance
  // (already applied elsewhere this session) says to replace, not tone
  // down.
  const [isEnteringChat, setIsEnteringChat] = useState(false);
  const [showLoadingScreen, setShowLoadingScreen] = useState(false);
  const enterChat = (href: string) => {
    if (reduceMotion) {
      router.push(href);
      return;
    }
    setIsEnteringChat(true);
    setShowLoadingScreen(true);
    window.setTimeout(() => router.push(href), CHAT_MORPH_MS);
  };

  // Every OTHER real navigation this page offers (header nav links, domain
  // chips, the Warung Watch chip, the "Explore Agents" secondary CTA) gets
  // the same loading-screen treatment as the hero CTA, minus the
  // /chat-specific header-morph — the opaque full-screen loader already
  // covers the header entirely, so there's nothing to gain from also
  // running that shape animation underneath it for a destination that
  // isn't /chat.
  const handleNavClick = (href: string, e: ReactMouseEvent<HTMLAnchorElement>) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    if (reduceMotion) {
      router.push(href);
      return;
    }
    setShowLoadingScreen(true);
    window.setTimeout(() => router.push(href), NAV_TRANSITION_MS);
  };

  const pageClass = isDark
    ? 'flex-1 min-h-0 overflow-y-auto bg-[#12151C] text-white'
    : 'flex-1 min-h-0 overflow-y-auto bg-nk-bg-warm text-zinc-900';
  const borderClass = isDark ? 'border-white/10' : 'border-zinc-200';
  const mutedText = isDark ? 'text-zinc-300' : 'text-zinc-600';
  const sectionTitle = isDark ? 'text-zinc-200' : 'text-zinc-800';
  const domainPillClass = isDark
    ? 'border-nk-official/40 text-nk-official bg-nk-official/10'
    : 'border-nk-official/30 text-nk-official-dim bg-nk-official/10';
  const tagBorderClass = isDark ? 'border-nk-official/40' : 'border-nk-official/30';
  const footerText = isDark ? 'text-zinc-500' : 'text-zinc-500';
  const footerTitle = isDark ? 'text-zinc-300' : 'text-zinc-700';

  return (
    <div className={`relative flex flex-col font-sans ${pageClass}`}>
      {/* The one real navigation this page triggers (hero "Mula Bertanya" →
          /chat) gets a full-screen transition treatment instead of a blank
          frame while the route change lands — see PageLoadingScreen's own
          docstring for why this isn't attached to every button on the
          page (toggles/modals don't navigate anywhere). */}
      <PageLoadingScreen show={showLoadingScreen} />

      {/* Two-tone ambient glow (official blue + heritage terracotta) instead
          of one flat blue blob — a small step toward the section-to-section
          "color storytelling" explored from the Fixa/V7 references: still a
          single quiet moment behind the hero (not a saturated per-section
          repaint, which would fight this product's restrained register),
          but it now carries both of NakTahu's identity accents instead of
          only the functional blue. */}
      <div
        aria-hidden
        className={`pointer-events-none absolute inset-x-0 top-0 h-[560px] overflow-hidden ${
          isDark ? 'opacity-100' : 'opacity-70'
        }`}
      >
        <div
          className={`absolute left-1/2 top-[-180px] h-[520px] w-[820px] -translate-x-1/2 rounded-full blur-3xl ${
            isDark
              ? 'bg-[radial-gradient(closest-side,rgba(37,99,235,0.22),transparent)]'
              : 'bg-[radial-gradient(closest-side,rgba(37,99,235,0.12),transparent)]'
          }`}
        />
        <div
          className={`absolute left-[68%] top-[-60px] h-[360px] w-[520px] -translate-x-1/2 rounded-full blur-3xl ${
            isDark
              ? 'bg-[radial-gradient(closest-side,rgba(224,141,91,0.14),transparent)]'
              : 'bg-[radial-gradient(closest-side,rgba(156,74,42,0.07),transparent)]'
          }`}
        />
      </div>

      <LandingHeader collapsing={isEnteringChat} onNavClick={handleNavClick} />

      {/* Everything below the header fades+blurs+scales out while the
          header morphs into the sidebar shape, then router.push fires —
          the same "materialize/dematerialize a whole surface" treatment
          apple-design's materials guidance describes for a big reposition,
          not a plain instant navigation. */}
      <motion.div
        animate={
          isEnteringChat
            ? { opacity: 0, scale: 0.98, filter: 'blur(8px)' }
            : { opacity: 1, scale: 1, filter: 'blur(0px)' }
        }
        transition={{ duration: CHAT_MORPH_MS / 1000, ease: 'easeOut' }}
        style={{ pointerEvents: isEnteringChat ? 'none' : undefined }}
      >
      <AuthErrorBanner />

      <HomeHero onEnterChat={enterChat} />

      <div className="mx-auto flex w-full max-w-6xl justify-center px-4 pb-14 sm:px-6">
        <PostcodePersonalizer
          className={`flex flex-wrap items-center justify-center gap-2 ${mutedText}`}
          inputClassName={`w-56 text-center border rounded-full px-3.5 py-1.5 text-xs font-medium locale-nowrap transition-colors ${domainPillClass}`}
        />
      </div>

      <motion.section
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className={`px-4 sm:px-6 py-16 sm:py-20 border-t ${borderClass} max-w-6xl mx-auto w-full`}
      >
        <h2 className={`text-center text-xl sm:text-2xl font-bold font-display mb-10 sm:mb-12 locale-text-balance ${sectionTitle}`}>
          {t('landing.features.title')}
        </h2>
        <LandingFeatureShowcase isDark={isDark} />
      </motion.section>

      <motion.section
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className={`px-4 sm:px-6 py-14 sm:py-16 border-t ${borderClass} max-w-6xl mx-auto w-full`}
      >
        <div className="text-center mb-8 sm:mb-10 max-w-xl mx-auto">
          <h2 className={`text-xl sm:text-2xl font-bold font-display mb-2 locale-text-balance ${sectionTitle}`}>
            {t('landing.preview.title')}
          </h2>
          <p className={`text-sm locale-text-balance ${mutedText}`}>{t('landing.preview.desc')}</p>
        </div>
        <InteractiveAnswerPreview isDark={isDark} />
      </motion.section>

      <motion.section
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className={`px-4 sm:px-6 py-14 sm:py-16 border-t ${borderClass} max-w-6xl mx-auto w-full`}
      >
        <div className="text-center mb-8 sm:mb-10 max-w-xl mx-auto">
          <h2 className={`text-xl sm:text-2xl font-bold font-display mb-2 locale-text-balance ${sectionTitle}`}>
            {t('landing.trust.title')}
          </h2>
          {/* Same inline-bold-highlight technique as the hero headline above
              (indexOf a marked substring, wrap it in a heavier span) — V7's
              "bold the keywords that matter, inline" pattern applied to the
              one sentence on this page making the sourcing claim, instead of
              only saying it via the chip grid below. */}
          <p className={`text-sm locale-text-balance ${mutedText}`}>
            {(() => {
              const desc = t('landing.trust.desc');
              const highlight = t('landing.trust.desc.highlight');
              const idx = desc.indexOf(highlight);
              if (idx === -1) return desc;
              return (
                <>
                  {desc.slice(0, idx)}
                  <span className={`font-semibold ${isDark ? 'text-zinc-200' : 'text-zinc-800'}`}>{highlight}</span>
                  {desc.slice(idx + highlight.length)}
                </>
              );
            })()}
          </p>
        </div>
        <AgencyTrustGrid isDark={isDark} />
      </motion.section>

      <motion.section
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className={`px-4 sm:px-6 py-14 sm:py-16 border-t ${borderClass} max-w-6xl mx-auto w-full`}
      >
        <div className="text-center mb-8 sm:mb-10 max-w-xl mx-auto">
          <h2 className={`text-xl sm:text-2xl font-bold font-display mb-2 locale-text-balance ${sectionTitle}`}>
            {t('landing.spotlight.title')}
          </h2>
          <p className={`text-sm locale-text-balance ${mutedText}`}>{t('landing.spotlight.desc')}</p>
        </div>
        <AgentSpotlight isDark={isDark} />
        <div className="mt-6 max-w-2xl mx-auto">
          <Callout variant="warning">
            <CalloutContent className="text-xs locale-text-balance">
              {t('landing.spotlight.disclaimer')}
            </CalloutContent>
          </Callout>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className={`px-4 sm:px-6 py-14 sm:py-16 border-t ${borderClass} max-w-6xl mx-auto w-full`}
      >
        <h2 className={`text-center text-xl sm:text-2xl font-bold font-display mb-8 sm:mb-10 locale-text-balance ${sectionTitle}`}>
          {t('landing.compare.title')}
        </h2>
        <ComparisonSection isDark={isDark} />
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.5 }}
        className={`px-4 sm:px-6 py-14 sm:py-16 border-t ${borderClass} flex flex-col items-center gap-6 max-w-6xl mx-auto w-full`}
      >
        <h2 className={`text-xl sm:text-2xl font-bold font-display locale-text-balance ${sectionTitle}`}>
          {t('landing.domains.title')}
        </h2>
        <div className="flex flex-wrap justify-center gap-2 sm:gap-3 max-w-2xl">
          {ALL_DOMAINS.map((d, i) => (
            <motion.span
              key={d.key}
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              whileHover={{ y: -2, scale: 1.03 }}
              transition={{ delay: i * 0.06, duration: 0.3 }}
              className="rounded-full locale-nowrap transition-shadow hover:shadow-md"
            >
              <Tag variant="primary" mode="pill" size="large" className={`text-sm px-3 sm:px-4 ${tagBorderClass}`}>
                {t(`domain.${d.key}`)}
              </Tag>
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
              href="https://github.com/timothylee58/naktahu-AI"
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
      </motion.div>
    </div>
  );
}
