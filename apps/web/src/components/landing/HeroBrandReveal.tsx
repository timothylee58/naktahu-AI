'use client';

import { motion, useReducedMotion } from 'framer-motion';

// Live CSS/SVG hero-opener moment — the mark assembling once on page load,
// followed by three citation-chip motifs. Built as a real, interactive
// React/Framer-Motion component (no rendered video asset): same visual
// concept originally scoped for a Remotion-rendered hero clip, but that
// path was blocked (this sandbox's network policy rejects the Chromium
// download Remotion needs to render), so this delivers the same "hero is a
// thesis" opening moment live instead.
//
// Deliberately NOT a second full-bleed media panel / two-column layout —
// this is a compact addition sitting *above* the existing hero content in
// the single-column hero LandingClient already reverted to, not a
// reintroduction of the seasonal two-panel video-hero layout this repo
// just moved away from.
//
// Mark geometry/colors are byte-identical to NakTahuMark.tsx's default
// (non-seasonal) SVG — this is the same permanent brand mark, just played
// as a one-time assembly instead of rendered static. Citation-chip motifs
// use the exact double-border "stamp" language CitationChip.tsx uses for
// real citations, holding three agency abbreviations already cited
// elsewhere in the product (AgencyTrustGrid.tsx) — never fabricated.

const PETAL_ROTATIONS = [0, 72, 144, 216, 288] as const;
const CHIP_AGENCIES = ['LHDN', 'KWSP', 'JPN'] as const;

// apple-design defaults: critically damped (no overshoot) for a
// materializing UI element, since nothing here carries gesture momentum.
const materialize = { type: 'spring' as const, damping: 22, stiffness: 260, mass: 0.6 };

export function HeroBrandReveal() {
  const reduceMotion = useReducedMotion();

  // Reduced motion: a single quick cross-fade to the fully-settled state,
  // no stagger/scale drama — apple-design's guidance for replacing
  // spring/parallax with a gentler, non-vestibular equivalent rather than
  // just turning feedback off entirely.
  const petalTransition = (i: number) =>
    reduceMotion ? { duration: 0.2 } : { ...materialize, delay: 0.15 + i * 0.06 };
  const chipTransition = (i: number) =>
    reduceMotion ? { duration: 0.2, delay: 0.1 } : { ...materialize, delay: 0.55 + i * 0.08 };

  return (
    <div aria-hidden className="flex flex-col items-center gap-4">
      <motion.svg
        viewBox="0 0 120 120"
        width={72}
        height={72}
        initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.7 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={reduceMotion ? { duration: 0.2 } : materialize}
      >
        <rect x="14" y="14" width="92" height="74" rx="30" fill="var(--brand-blue, #3B5BFF)" />
        <motion.path
          d="M32 88 L32 108 L52 88 Z"
          fill="var(--brand-blue, #3B5BFF)"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={reduceMotion ? { duration: 0.2 } : { ...materialize, delay: 0.08 }}
        />
        <g>
          {PETAL_ROTATIONS.map((rot, i) => (
            <motion.ellipse
              key={rot}
              cx={98}
              cy={17}
              rx="6.5"
              ry="9"
              fill="#ED1C24"
              transform={`rotate(${rot} 98 26)`}
              style={{ transformOrigin: '98px 26px' }}
              initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={petalTransition(i)}
            />
          ))}
          <motion.g
            initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={petalTransition(5)}
            style={{ transformOrigin: '98px 26px' }}
          >
            <circle cx={98} cy={26} r="3" fill="#C4141A" />
            <line x1={98} y1={26} x2={108} y2={13} stroke="#C4141A" strokeWidth="1.4" strokeLinecap="round" />
            <circle cx={108} cy={13} r="1.8" fill="#FFCC00" />
          </motion.g>
        </g>
      </motion.svg>

      <div className="flex flex-wrap justify-center gap-2">
        {CHIP_AGENCIES.map((agency, i) => (
          <motion.span
            key={agency}
            initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 6, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={chipTransition(i)}
            className="inline-flex items-center rounded-md border-2 border-double border-nk-official/50 bg-nk-official/5 text-nk-official-dim px-2.5 py-0.5 text-[11px] font-mono font-semibold uppercase tracking-tight dark:bg-nk-official/10 dark:border-nk-official/40 dark:text-nk-official"
          >
            {agency}
          </motion.span>
        ))}
      </div>
    </div>
  );
}
