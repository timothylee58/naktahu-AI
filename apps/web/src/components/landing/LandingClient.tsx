'use client';

import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from 'framer-motion';
import { AuthErrorBanner } from '@/components/auth/AuthErrorBanner';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { TypewriterQueryWrapper } from './TypewriterQueryWrapper';
import { LandingFeatureShowcase } from './LandingFeatureShowcase';
import { AgencyTrustGrid } from './AgencyTrustGrid';
import { AgentSpotlight } from './AgentSpotlight';
import { ComparisonSection } from './ComparisonSection';
import { InteractiveAnswerPreview } from './InteractiveAnswerPreview';
import { SeasonalHeroVideo } from './SeasonalHeroVideo';
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

// Interactive hero chips — each is a real, functioning shortcut: domain
// chips prefill /chat with a representative query for that domain (see
// app/chat/page.tsx's ?q= handling), and the Warung Watch chip links
// straight to its own page rather than into chat, since it isn't a RAG
// domain.
// Trimmed to a representative spread (gov/finance, business, personal) —
// the full 10-domain list is already one scroll away in "Knowledge
// Domains" below; the hero chips are a taste, not the whole menu.
const DOMAIN_CHIPS = [
  { key: 'tax', queryKey: 'landing.chip.tax.query' },
  { key: 'business', queryKey: 'landing.chip.business.query' },
  { key: 'immigration', queryKey: 'landing.chip.immigration.query' },
] as const;

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

  // framer's useReducedMotion() is false on the server and updates
  // post-mount on the client — safe here because every value it gates
  // below only ever changes a `style` transform amount or whether an
  // event listener is attached, never which DOM nodes render, so there's
  // nothing for a server/client markup diff to catch (same reasoning
  // ChatInput/PromptChips/ChatAmbientMesh already document for their own
  // client-only season/motion checks elsewhere in this codebase).
  const reduceMotion = useReducedMotion();

  // ── Scroll parallax: two ambient glow blobs drift at different speeds
  // as the hero scrolls out of view. Scoped to the hero section itself
  // (not the whole page's scroll range) via `target`, so the effect is
  // "hero leaving the viewport", not "how far down the whole page you are".
  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress: heroScroll } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  });
  // Background blob (larger, sits further back visually) drifts less;
  // foreground blob (smaller, heritage accent) drifts more — the classic
  // depth cue where the nearer layer appears to move faster.
  const glowBgY = useTransform(heroScroll, [0, 1], reduceMotion ? [0, 0] : [0, 60]);
  const glowFgY = useTransform(heroScroll, [0, 1], reduceMotion ? [0, 0] : [0, 160]);

  // ── Mouse tilt: raw pointer offset from the hero's center (-0.5..0.5 on
  // each axis), sprung for a natural settle instead of snapping 1:1 to the
  // cursor — springs are interruptible and velocity-aware (apple-design
  // guidance already applied elsewhere in this codebase), which matters
  // here since the pointer can reverse direction at any instant.
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const springX = useSpring(pointerX, { stiffness: 150, damping: 20, mass: 0.5 });
  const springY = useSpring(pointerY, { stiffness: 150, damping: 20, mass: 0.5 });
  const tiltRotateX = useTransform(springY, [-0.5, 0.5], reduceMotion ? [0, 0] : [6, -6]);
  const tiltRotateY = useTransform(springX, [-0.5, 0.5], reduceMotion ? [0, 0] : [-6, 6]);
  const glowBgX = useTransform(springX, [-0.5, 0.5], reduceMotion ? [0, 0] : [-16, 16]);
  const glowFgX = useTransform(springX, [-0.5, 0.5], reduceMotion ? [0, 0] : [24, -24]);

  const handleHeroMouseMove = (e: ReactMouseEvent<HTMLElement>) => {
    if (reduceMotion) return; // never attach real work behind a no-op listener
    const rect = e.currentTarget.getBoundingClientRect();
    pointerX.set((e.clientX - rect.left) / rect.width - 0.5);
    pointerY.set((e.clientY - rect.top) / rect.height - 0.5);
  };
  const handleHeroMouseLeave = () => {
    pointerX.set(0);
    pointerY.set(0);
  };

  // ── Header → sidebar chat-morph. reduceMotion skips straight to
  // navigation — a shape-morphing header is exactly the kind of large
  // moving-object transition apple-design's reduced-motion guidance
  // (already applied elsewhere this session) says to replace, not tone
  // down.
  const [isEnteringChat, setIsEnteringChat] = useState(false);
  const handleStartChat = (e: ReactMouseEvent<HTMLAnchorElement>) => {
    // Modified clicks (open in new tab/window, middle-click) must keep
    // working exactly like a plain <a href>/<Link> — only a plain left
    // click gets the custom transition.
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    if (reduceMotion) {
      router.push('/chat');
      return;
    }
    setIsEnteringChat(true);
    window.setTimeout(() => router.push('/chat'), CHAT_MORPH_MS);
  };

  const pageClass = isDark
    ? 'flex-1 min-h-0 overflow-y-auto bg-[#12151C] text-white'
    : 'flex-1 min-h-0 overflow-y-auto bg-nk-bg-warm text-zinc-900';
  const borderClass = isDark ? 'border-white/10' : 'border-zinc-200';
  const mutedText = isDark ? 'text-zinc-400' : 'text-zinc-600';
  const sectionTitle = isDark ? 'text-zinc-200' : 'text-zinc-800';
  const searchBoxClass = isDark
    ? 'bg-white/5 border-white/10 shadow-[0_8px_30px_rgba(0,0,0,0.35)] focus-within:border-nk-official/50'
    : 'bg-white border-zinc-200 shadow-[0_2px_16px_rgba(15,23,42,0.06)] focus-within:border-nk-official/40';
  const domainPillClass = isDark
    ? 'border-nk-official/40 text-nk-official bg-nk-official/10'
    : 'border-nk-official/30 text-nk-official-dim bg-nk-official/10';
  const footerText = isDark ? 'text-zinc-500' : 'text-zinc-500';
  const footerTitle = isDark ? 'text-zinc-300' : 'text-zinc-700';

  return (
    <div className={`relative flex flex-col font-sans ${pageClass}`}>
      {/* Two-tone ambient glow (official blue + heritage terracotta) instead
          of one flat blue blob — a small step toward the section-to-section
          "color storytelling" explored from the Fixa/V7 references: still a
          single quiet moment behind the hero (not a saturated per-section
          repaint, which would fight this product's restrained register),
          but it now carries both of NakTahu's identity accents instead of
          only the functional blue. */}
      <motion.div
        aria-hidden
        style={{ y: glowBgY, x: glowBgX }}
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
      </motion.div>
      {/* Foreground blob on its own transform, independent of the background
          one above — a different scroll speed and a larger mouse nudge is
          what reads as "in front of" the other blob. */}
      <motion.div
        aria-hidden
        style={{ y: glowFgY, x: glowFgX }}
        className={`pointer-events-none absolute inset-x-0 top-0 h-[560px] overflow-hidden ${
          isDark ? 'opacity-100' : 'opacity-70'
        }`}
      >
        <div
          className={`absolute left-[68%] top-[-60px] h-[360px] w-[520px] -translate-x-1/2 rounded-full blur-3xl ${
            isDark
              ? 'bg-[radial-gradient(closest-side,rgba(224,141,91,0.14),transparent)]'
              : 'bg-[radial-gradient(closest-side,rgba(156,74,42,0.07),transparent)]'
          }`}
        />
      </motion.div>

      <LandingHeader collapsing={isEnteringChat} />

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

      <section
        ref={heroRef}
        onMouseMove={handleHeroMouseMove}
        onMouseLeave={handleHeroMouseLeave}
        style={{ perspective: 800 }}
        className="relative flex flex-col items-center justify-center flex-1 text-center px-4 sm:px-6 py-16 sm:py-24 gap-6 sm:gap-8 max-w-6xl mx-auto w-full"
      >
        <SeasonalHeroVideo />
        {/* Springed 3D tilt on the whole content group — `contents` keeps
            each child's own fadeUp entrance untouched, this just adds the
            tilt transform as an ancestor. */}
        <motion.div style={{ rotateX: tiltRotateX, rotateY: tiltRotateY }} className="contents">
        <motion.div
          custom={0}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className="inline-flex items-center gap-2 text-xs font-semibold tracking-widest text-nk-official uppercase border border-nk-official/30 rounded-full px-4 py-1.5 locale-nowrap"
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
                <span className="text-nk-official font-extrabold">{highlight}</span>
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
          className={`w-full max-w-xl border rounded-2xl px-4 sm:px-5 py-3.5 sm:py-4 flex items-center gap-3 transition-colors duration-200 ${searchBoxClass}`}
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

        {/* Trust disclaimer — moved from above the headline (where it
            competed with it for first-glance attention) to a quiet
            footnote right under the input, where a first-time visitor
            actually needs it: the moment before they type. */}
        <motion.p
          custom={4}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className={`text-xs max-w-md -mt-2 locale-text-balance ${mutedText}`}
        >
          {t('landing.hero.disclaimer_note')}
        </motion.p>

        <motion.div
          custom={5}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className="flex flex-wrap justify-center gap-2 max-w-xl"
        >
          {DOMAIN_CHIPS.map((chip) => (
            <Link
              key={chip.key}
              href={`/chat?q=${encodeURIComponent(t(chip.queryKey))}`}
              className={`border rounded-full px-3 py-1 text-xs font-medium locale-nowrap transition-all hover:-translate-y-0.5 hover:shadow-sm ${domainPillClass}`}
            >
              {t(`domain.${chip.key}`)}
            </Link>
          ))}
          <Link
            href="/warung-watch"
            className={`border rounded-full px-3 py-1 text-xs font-medium locale-nowrap transition-all hover:-translate-y-0.5 hover:shadow-sm ${domainPillClass}`}
          >
            {t('nav.warung_watch')}
          </Link>
        </motion.div>

        <motion.div
          custom={6}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          className="flex flex-col items-center gap-3"
        >
          <Link
            href="/chat"
            onClick={handleStartChat}
            className="inline-flex items-center gap-2 bg-nk-official hover:bg-nk-official-dim hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white font-semibold px-6 sm:px-8 py-3 sm:py-3.5 rounded-full text-sm sm:text-base shadow-lg shadow-blue-900/30 locale-nowrap"
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
          {/* Single secondary link instead of two stacked links (Explore
              Agents + a separate pricing-note row) — freemium pricing is
              one click away via the "Pricing" nav item and on /agents
              itself; the hero doesn't need to restate it. */}
          <Link
            href="/agents"
            className="text-sm hover:text-nk-official transition-colors locale-nowrap"
          >
            {t('landing.hero.secondary_cta')}
          </Link>
        </motion.div>
        </motion.div>
      </section>

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
              className={`border rounded-full px-3 sm:px-4 py-1.5 text-sm font-medium locale-nowrap transition-shadow hover:shadow-md ${domainPillClass}`}
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
