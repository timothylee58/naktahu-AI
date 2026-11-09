'use client';

import { useEffect, useState, type MouseEvent as ReactMouseEvent } from 'react';
import { useRouter } from 'next/navigation';
import { motion, useReducedMotion } from 'framer-motion';
import { Callout, CalloutContent } from '@govtechmy/myds-react/callout';
import { AuthErrorBanner } from '@/components/auth/AuthErrorBanner';
import { PageLoadingScreen } from '@/components/ui/PageLoadingScreen';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { HomeHero } from '@/components/home/HomeHero';
import { AgencyTrustGrid } from './AgencyTrustGrid';
import { AgentSpotlight } from './AgentSpotlight';
import { TaskDemoCards } from './TaskDemoCards';
import { SectionHeading } from './SectionHeading';
import { TrustStrip } from './TrustStrip';
import { LandingFooter } from './LandingFooter';
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

      <TrustStrip />

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

      <main id="main-content" tabIndex={-1} className="focus:outline-none">
      <HomeHero onEnterChat={enterChat} />

      {/* Task demos + agency sources as one "proof" section: watching a
          question become a cited answer IS the trust argument. Pausable,
          auto-playing cards (america.gov/coming-soon pattern) replace both
          the old feature showcase and the single tabbed preview. */}
      <motion.section
        aria-labelledby="landing-proof"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20"
      >
        <SectionHeading
          id="landing-proof"
          title={t('landing.proof.title')}
          description={t('landing.proof.desc')}
        />
        <TaskDemoCards />
        <div className="mt-16">
          <h3 className="font-display text-xl font-bold text-nk-ink sm:text-2xl locale-text-balance">
            {t('landing.trust.title')}
          </h3>
          <p className="mb-6 mt-2 max-w-2xl text-base leading-relaxed text-nk-ink/80 locale-text-balance">
            {(() => {
              const desc = t('landing.trust.desc');
              const highlight = t('landing.trust.desc.highlight');
              const idx = desc.indexOf(highlight);
              if (idx === -1) return desc;
              return (
                <>
                  {desc.slice(0, idx)}
                  <span className="font-semibold text-nk-ink">{highlight}</span>
                  {desc.slice(idx + highlight.length)}
                </>
              );
            })()}
          </p>
          <AgencyTrustGrid isDark={isDark} />
        </div>
      </motion.section>

      {/* Full-bleed tinted band — the one section that breaks the max-w
          column, so the page has rhythm instead of identical stacked boxes. */}
      <motion.section
        aria-labelledby="landing-spotlight"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true, margin: '-80px' }}
        transition={{ duration: 0.6 }}
        className="border-y border-[var(--nk-border)] bg-nk-card"
      >
        <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 sm:py-20">
          <SectionHeading
            id="landing-spotlight"
            title={t('landing.spotlight.title')}
            description={t('landing.spotlight.desc')}
          />
          <AgentSpotlight isDark={isDark} />
          <div className="mt-8 max-w-2xl">
            <Callout variant="warning">
              <CalloutContent className="text-sm locale-text-balance">
                {t('landing.spotlight.disclaimer')}
              </CalloutContent>
            </Callout>
          </div>
        </div>
      </motion.section>

      </main>

      <LandingFooter tagline={tagline} />
      </motion.div>
    </div>
  );
}
