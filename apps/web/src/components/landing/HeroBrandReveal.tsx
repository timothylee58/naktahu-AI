'use client';

import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'framer-motion';

// Hero opener — "orbit of sources": six real Malaysian agencies circling the
// brand mark on a tilted elliptical path, passing in front of and behind it.
//
// Why an orbit and not a static row: the previous version stacked a 72px flat
// mark over a plain row of three chips. Two problems that version had, both
// visible on the live page — the mark duplicated the header logo sitting a few
// hundred pixels directly above it in the same viewport, and the chips made
// the "verified official sources" claim in words without ever *showing* it.
// Putting the agencies in continuous orbit around the mark states the
// product's actual thesis structurally: many official sources, one answer at
// the centre. The mark here is the subject of a diagram, not a second logo,
// which is what earns the repeat.
//
// Motion vocabulary, per the three references this was designed against:
//   - Mobbin (Notion's web hero): tiles travelling curved paths around the
//     centre content, rather than parked in a grid.
//   - three.js: perspective depth — orbiting objects scale up and brighten
//     toward the camera, shrink and dim behind the subject, and actually
//     occlude (z-index flips at the half-orbit). Done with 2D scale rather
//     than real translateZ on purpose: a perspective transform on 11px
//     monospace text renders it visibly soft, and legibility of the agency
//     names is the whole point of the element.
//   - Remotion: ONE master clock. Every value below is derived from a single
//     frame counter via interpolate(), the way a Remotion composition derives
//     everything from useCurrentFrame() — so the entrance, the orbit and the
//     mark's breathing are phase-locked into one choreographed sequence
//     instead of N independent CSS animations drifting apart.
//
// The rAF loop writes transform/opacity straight to the DOM through refs and
// never calls setState, so this animates on the compositor and triggers zero
// React re-renders after mount.
//
// Agency names are the six real agencies AgencyTrustGrid.tsx already names as
// this product's sources — never invented ones. Chip styling is the same
// double-border "stamp" language CitationChip.tsx uses for real citations.

const AGENCIES = ['LHDN', 'KWSP', 'SSM', 'PERKESO', 'KKM', 'JPN'] as const;

const FPS = 60;
const TAU = Math.PI * 2;
/** Seconds for one full revolution. Slow enough to read as ambient rather
 *  than busy; 24s ≈ 0.04Hz, far below the ~0.2Hz band that reads as
 *  vestibularly unpleasant for large sustained motion. */
const ORBIT_SECONDS = 24;
/** Entrance: chips converge inward from a wider radius into the orbit. */
const INTRO_FRAMES = 1.15 * FPS;
const INTRO_STAGGER = 0.07 * FPS;

/** Vertical radius. Kept at ~1/3 of the horizontal radius rather than flatter:
 *  below about that ratio the ellipse stops reading as a path at all and the
 *  chips just look scattered at random heights. */
const ORBIT_RY = 44;
const MARK_SIZE = 78;
const BOX_HEIGHT = 150;

/** Remotion's interpolate(), clamped: map a frame onto an output range. */
function interpolate(frame: number, [inMin, inMax]: [number, number], [outMin, outMax]: [number, number]) {
  if (inMax === inMin) return outMin;
  const p = Math.min(1, Math.max(0, (frame - inMin) / (inMax - inMin)));
  return outMin + (outMax - outMin) * p;
}

/** Critically-damped settle — apple-design's default for a materializing
 *  element that carries no gesture momentum, so no overshoot. */
function easeOutCubic(p: number) {
  return 1 - Math.pow(1 - p, 3);
}

export function HeroBrandReveal() {
  const reduceMotion = useReducedMotion();
  const boxRef = useRef<HTMLDivElement>(null);
  const markRef = useRef<HTMLDivElement>(null);
  const chipRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    // Reduced motion: no clock at all. Chips settle at their rest angles and
    // simply fade in — a gentler, non-vestibular equivalent rather than no
    // feedback, per apple-design's reduced-motion guidance.
    if (reduceMotion) {
      chipRefs.current.forEach((el, i) => {
        if (!el) return;
        const theta = (i / AGENCIES.length) * TAU;
        const rx = orbitRadius(boxRef.current);
        el.style.transform = `translate(-50%, -50%) translate(${Math.cos(theta) * rx}px, ${Math.sin(theta) * ORBIT_RY}px)`;
        el.style.opacity = '1';
      });
      if (markRef.current) markRef.current.style.opacity = '1';
      return;
    }

    let raf = 0;
    let startTs: number | null = null;

    const tick = (ts: number) => {
      if (startTs === null) startTs = ts;
      const frame = ((ts - startTs) / 1000) * FPS;
      const rx = orbitRadius(boxRef.current);

      // Mark: materializes first, then breathes on the orbit's own period so
      // the two stay phase-locked (the Remotion single-clock point).
      if (markRef.current) {
        const intro = easeOutCubic(interpolate(frame, [0, INTRO_FRAMES], [0, 1]));
        const breathe = 1 + Math.sin((frame / (ORBIT_SECONDS * FPS)) * TAU) * 0.02;
        markRef.current.style.opacity = String(intro);
        markRef.current.style.transform = `translate(-50%, -50%) scale(${(0.82 + 0.18 * intro) * breathe})`;
      }

      chipRefs.current.forEach((el, i) => {
        if (!el) return;
        const introStart = INTRO_FRAMES * 0.35 + i * INTRO_STAGGER;
        const intro = easeOutCubic(interpolate(frame, [introStart, introStart + INTRO_FRAMES], [0, 1]));

        const theta = (i / AGENCIES.length) * TAU + (frame / (ORBIT_SECONDS * FPS)) * TAU;
        // depth: -1 fully behind the mark, +1 fully in front of it.
        const depth = Math.sin(theta);
        const near = (depth + 1) / 2;

        // Expand outward: chips emerge from behind the mark and settle onto
        // the ring. Deliberately outward rather than converging in from a
        // wider radius — an inward entrance peaks ABOVE the settled radius,
        // and orbitRadius()'s inset only guarantees the settled ring fits.
        // Measured at 1.45x inward it pushed ~5px past the viewport edge at
        // 390px width for ~2s on every load (Cursor Bugbot flagged the
        // mechanism on PR #206). Scaling 0.55 -> 1.0 can never exceed the
        // settled radius, so the ring fits by construction at any width.
        const radius = rx * (0.55 + 0.45 * intro);
        const x = Math.cos(theta) * radius;
        const y = depth * ORBIT_RY * (0.6 + 0.4 * intro);

        // Depth floors are deliberately shallow: enough contrast between the
        // near and far halves to read as 3D, but the far side still has to be
        // legible — these are the agency names the element exists to show, so
        // fading them to near-invisible would trade the point for the effect.
        el.style.transform =
          `translate(-50%, -50%) translate(${x}px, ${y}px) scale(${(0.82 + 0.2 * near) * (0.9 + 0.1 * intro)})`;
        el.style.opacity = String((0.56 + 0.44 * near) * intro);
        // Real occlusion: the far half of the orbit passes behind the mark.
        el.style.zIndex = depth >= 0 ? '20' : '0';
      });

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [reduceMotion]);

  return (
    <div
      ref={boxRef}
      aria-hidden
      className="relative w-full max-w-md select-none"
      style={{ height: BOX_HEIGHT }}
    >
      {/* Depth glow under the mark — the one light source in the composition,
          so the orbiting chips read as circling something with presence. */}
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-48 w-48 -translate-x-1/2 -translate-y-1/2 rounded-full blur-2xl"
        style={{ background: 'radial-gradient(closest-side, rgba(59,91,255,0.55), rgba(59,91,255,0.12) 55%, transparent)' }}
      />

      {/* The mark — same geometry as NakTahuMark.tsx's permanent bunga-raya
          mark, at z-10 so half the orbit passes in front and half behind. */}
      <div
        ref={markRef}
        className="absolute left-1/2 top-1/2 z-10"
        style={{ opacity: 0, transform: 'translate(-50%, -50%)', willChange: 'transform, opacity' }}
      >
        <svg viewBox="0 0 120 120" width={MARK_SIZE} height={MARK_SIZE}>
          <rect x="14" y="14" width="92" height="74" rx="30" fill="var(--brand-blue, #3B5BFF)" />
          <path d="M32 88 L32 108 L52 88 Z" fill="var(--brand-blue, #3B5BFF)" />
          <g>
            {[0, 72, 144, 216, 288].map((rot) => (
              <ellipse
                key={rot}
                cx={98}
                cy={17}
                rx="6.5"
                ry="9"
                fill="#ED1C24"
                transform={`rotate(${rot} 98 26)`}
              />
            ))}
            <circle cx={98} cy={26} r="3" fill="#C4141A" />
            <line x1={98} y1={26} x2={108} y2={13} stroke="#C4141A" strokeWidth="1.4" strokeLinecap="round" />
            <circle cx={108} cy={13} r="1.8" fill="#FFCC00" />
          </g>
        </svg>
      </div>

      {AGENCIES.map((agency, i) => (
        <div
          key={agency}
          ref={(el) => {
            chipRefs.current[i] = el;
          }}
          className="absolute left-1/2 top-1/2"
          style={{ opacity: 0, transform: 'translate(-50%, -50%)', willChange: 'transform, opacity' }}
        >
          <span className="inline-flex items-center whitespace-nowrap rounded-md border-2 border-double border-nk-official/50 bg-nk-official/5 px-2 py-0.5 text-[10px] font-mono font-semibold uppercase tracking-tight text-nk-official-dim backdrop-blur-sm dark:border-nk-official/40 dark:bg-nk-official/10 dark:text-nk-official">
            {agency}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Horizontal orbit radius, derived from the element's real width so the ring
 *  never overflows a narrow phone viewport. Falls back to a safe default
 *  before first measurement. */
function orbitRadius(box: HTMLDivElement | null) {
  const width = box?.clientWidth ?? 320;
  // Capped well inside the hero's text column: a ring wider than the headline
  // below it stops reading as part of the same composition.
  return Math.max(92, Math.min(128, width / 2 - 58));
}
