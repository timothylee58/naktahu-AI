'use client';

import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'framer-motion';

// /chat empty state opener — the loading screen's brand logo, orbited by the
// six real agencies from the landing hero.
//
// This composes two treatments that already exist in the product rather than
// inventing a third:
//   - PageLoadingScreen.tsx's extruded 3D speech bubble (stacked translateZ
//     layers shaded front-to-back, bobbing and rotating on Y, with a bunga
//     raya badge orbiting it in real 3D). That is the mark users have just
//     seen a second earlier — LandingClient routes through the loading screen
//     on "Mula Bertanya" — so reusing it here makes /chat feel like the
//     destination of that transition instead of an unrelated screen.
//   - HeroBrandReveal.tsx's agency orbit: LHDN/KWSP/SSM/PERKESO/KKM/JPN on a
//     tilted ellipse, scaling and dimming with depth and actually passing
//     behind the mark at the half-orbit.
//
// The two clocks are deliberately different mechanisms and that is fine: the
// bubble's bob/spin/badge are pure CSS keyframes (no JS state, nothing to
// phase-lock against), while the agency ring needs a JS clock because its
// radius is derived from the measured box width every frame. The ring's rAF
// loop writes transform/opacity straight through refs — no setState, so zero
// React re-renders after mount — and is gated by an IntersectionObserver so
// it costs nothing once a conversation starts and scrolls this out of view.
//
// Replaces the 72px kawung roundel that sat here before. That roundel was a
// static abstract glyph; this states the same thesis the landing page states
// — many official sources, one answer at the centre — at the exact moment the
// user is deciding what to ask.

const AGENCIES = ['LHDN', 'KWSP', 'SSM', 'PERKESO', 'KKM', 'JPN'] as const;

const FPS = 60;
const TAU = Math.PI * 2;
/** One revolution. Same 24s as the landing hero: ~0.04Hz, well below the
 *  ~0.2Hz band that reads as vestibularly unpleasant for sustained motion. */
const ORBIT_SECONDS = 24;
const INTRO_FRAMES = 1.15 * FPS;
const INTRO_STAGGER = 0.07 * FPS;
/** Ellipse tilt — vertical radius as a fraction of the horizontal one. */
const ORBIT_RY_RATIO = 0.5;

const ACCENT = '#3B5BFF';
const RADIUS = '48% 48% 48% 6px / 52% 52% 52% 6px';
const BUBBLE_DEPTH = 12;
/** Bubble face size. Smaller than the loading screen's 190x165 — this sits
 *  inside a scrollable conversation column above a greeting and a prompt
 *  grid, not alone on a full-screen takeover. */
const BUBBLE_W = 88;
const BUBBLE_H = 76;

/** Remotion's interpolate(), clamped. */
function interpolate(frame: number, [inMin, inMax]: [number, number], [outMin, outMax]: [number, number]) {
  if (inMax === inMin) return outMin;
  const p = Math.min(1, Math.max(0, (frame - inMin) / (inMax - inMin)));
  return outMin + (outMax - outMin) * p;
}

/** Critically-damped settle — no overshoot, since nothing here carries
 *  gesture momentum (apple-design's default for a materializing element). */
function easeOutCubic(p: number) {
  return 1 - Math.pow(1 - p, 3);
}

/** Ring geometry derived continuously from the measured box width, so the
 *  composition scales with the viewport instead of stepping at breakpoints.
 *  The 54px inset keeps the widest chip (PERKESO) inside the box at the
 *  settled radius; the entrance only ever scales outward *to* that radius,
 *  never past it, so the ring fits by construction at any width. */
function orbitGeometry(box: HTMLDivElement | null) {
  const width = box?.clientWidth ?? 320;
  const rx = Math.max(96, Math.min(210, width / 2 - 54));
  return { rx, ry: rx * ORBIT_RY_RATIO };
}

export function ChatEmptyOrbit() {
  const reduceMotion = useReducedMotion();
  const boxRef = useRef<HTMLDivElement>(null);
  const chipRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    // Reduced motion: no clock at all. Chips sit at their rest angles, fully
    // opaque — a gentler static equivalent, not an absence of the element.
    if (reduceMotion) {
      const layoutStatic = () => {
        const { rx, ry } = orbitGeometry(boxRef.current);
        chipRefs.current.forEach((el, i) => {
          if (!el) return;
          const theta = (i / AGENCIES.length) * TAU;
          el.style.transform = `translate(-50%, -50%) translate(${Math.cos(theta) * rx}px, ${Math.sin(theta) * ry}px)`;
          el.style.opacity = '1';
        });
      };
      layoutStatic();
      window.addEventListener('resize', layoutStatic);
      return () => window.removeEventListener('resize', layoutStatic);
    }

    let raf = 0;
    let lastTs: number | null = null;
    let running = false;
    // Accumulated *visible* time, not wall clock: the orbit freezes while
    // off-screen rather than silently advancing behind the user's back.
    let elapsedMs = 0;

    const tick = (ts: number) => {
      // Clamped delta — a resumed rAF (hidden tab, stalled main thread) hands
      // back a timestamp far in the future, and without the clamp that single
      // frame would jump the orbit by the whole gap.
      elapsedMs += lastTs === null ? 0 : Math.min(ts - lastTs, 100);
      lastTs = ts;
      const frame = (elapsedMs / 1000) * FPS;
      const { rx, ry } = orbitGeometry(boxRef.current);

      chipRefs.current.forEach((el, i) => {
        if (!el) return;
        const introStart = INTRO_FRAMES * 0.35 + i * INTRO_STAGGER;
        const intro = easeOutCubic(interpolate(frame, [introStart, introStart + INTRO_FRAMES], [0, 1]));

        const theta = (i / AGENCIES.length) * TAU + (frame / (ORBIT_SECONDS * FPS)) * TAU;
        // depth: -1 fully behind the bubble, +1 fully in front of it.
        const depth = Math.sin(theta);
        const near = (depth + 1) / 2;

        const radius = rx * (0.55 + 0.45 * intro);
        const x = Math.cos(theta) * radius;
        const y = depth * ry * (0.6 + 0.4 * intro);

        // Shallow depth floors on purpose: enough near/far contrast to read
        // as 3D, while the far half stays legible — these agency names are
        // the point of the element, not decoration to fade out.
        el.style.transform =
          `translate(-50%, -50%) translate(${x}px, ${y}px) scale(${(0.84 + 0.18 * near) * (0.9 + 0.1 * intro)})`;
        el.style.opacity = String((0.58 + 0.42 * near) * intro);
        // Real occlusion: the far half passes behind the bubble (z-10).
        el.style.zIndex = depth >= 0 ? '20' : '0';
      });

      raf = requestAnimationFrame(tick);
    };

    const start = () => {
      if (running) return;
      running = true;
      // Drop the stale timestamp so the first frame after a resume
      // contributes a zero delta and the orbit resumes exactly where it was.
      lastTs = null;
      raf = requestAnimationFrame(tick);
    };
    const stop = () => {
      if (!running) return;
      running = false;
      cancelAnimationFrame(raf);
    };

    const box = boxRef.current;
    if (!box || typeof IntersectionObserver === 'undefined') {
      start();
      return () => stop();
    }

    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) start();
        else stop();
      },
      { threshold: 0 },
    );
    io.observe(box);

    return () => {
      io.disconnect();
      stop();
    };
  }, [reduceMotion]);

  // Extruded depth layers, shaded front-to-back — the loading screen's own
  // construction, at this surface's smaller scale.
  const layers = Array.from({ length: BUBBLE_DEPTH }, (_, i) => (
    <div
      key={i}
      style={{
        position: 'absolute',
        inset: 0,
        borderRadius: RADIUS,
        background: ACCENT,
        filter: `brightness(${0.32 + (i / (BUBBLE_DEPTH - 1)) * 0.4})`,
        transform: `translateZ(${-i * 1.7}px)`,
      }}
    />
  ));

  return (
    <div
      ref={boxRef}
      aria-hidden
      className="relative w-full max-w-md select-none h-[190px] sm:h-[220px] md:max-w-xl md:h-[260px]"
      style={{ perspective: 1000 }}
    >
      {/* Single light source under the mark, so the chips read as circling
          something with presence rather than floating on a flat panel. */}
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-52 w-52 sm:h-60 sm:w-60 -translate-x-1/2 -translate-y-1/2 rounded-full blur-2xl"
        style={{ background: `radial-gradient(closest-side, ${ACCENT}55, ${ACCENT}1A 55%, transparent)` }}
      />

      {/* The mark. z-10 so half the orbit passes in front and half behind. */}
      <div
        className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 md:scale-125"
        style={{ transformStyle: 'preserve-3d' }}
      >
        <div
          style={{
            transformStyle: 'preserve-3d',
            // Reduced motion resolves the bubble to its rest pose rather than
            // removing it: the composition still reads, it just holds still.
            animation: reduceMotion ? undefined : 'nk-chat-bob 7.5s ease-in-out infinite',
          }}
        >
          <div
            style={{
              transformStyle: 'preserve-3d',
              // A sway, NOT the loading screen's full rotateY spin. The full
              // spin is right for a 1.1s takeover, but this mark is on screen
              // for as long as the user takes to decide what to ask, and a
              // continuous revolution leaves it turned away — a featureless
              // blue blob with the three dots edge-on — for most of its
              // period. Verified by screenshot: the dots were never visible
              // in any sampled frame of the spinning version. Swaying ±17°
              // keeps the face readable while still showing the extrusion.
              animation: reduceMotion ? undefined : 'nk-chat-sway 9s ease-in-out infinite',
            }}
          >
            <div className="relative" style={{ width: BUBBLE_W, height: BUBBLE_H, transformStyle: 'preserve-3d' }}>
              {layers}
              <div
                className="absolute inset-0 flex items-center justify-center overflow-hidden"
                style={{
                  borderRadius: RADIUS,
                  background: `linear-gradient(150deg, ${ACCENT} 0%, #2A45D8 100%)`,
                  boxShadow: `0 0 34px -8px ${ACCENT}99, inset 0 2px 0 rgba(255,255,255,0.28)`,
                  transform: 'translateZ(2px)',
                }}
              >
                <div className="flex items-center gap-[7px]" style={{ transform: 'translateY(-4px)' }}>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="inline-block rounded-full bg-white"
                      style={{
                        width: 9,
                        height: 9,
                        opacity: reduceMotion ? 0.85 : undefined,
                        animation: reduceMotion ? undefined : `nk-chat-dot 1.35s ease-in-out ${i * 0.18}s infinite`,
                      }}
                    />
                  ))}
                </div>
                <div
                  className="pointer-events-none absolute inset-0"
                  style={{ background: 'linear-gradient(115deg, rgba(255,255,255,0.30) 0%, rgba(255,255,255,0) 46%)' }}
                />
              </div>
            </div>

            {/* Bunga raya badge orbiting the bubble in real 3D — the same
                5-petal + stamen construction as NakTahuMark, counter-rotated
                so the flower always faces the viewer. */}
            <div
              className="pointer-events-none absolute inset-0"
              style={{
                transformStyle: 'preserve-3d',
                animation: reduceMotion ? undefined : 'nk-chat-orbit 6s linear infinite',
              }}
            >
              <div
                className="absolute"
                style={{
                  top: 2,
                  left: '50%',
                  marginLeft: 22,
                  width: 26,
                  height: 26,
                  transform: 'translateZ(40px)',
                  transformStyle: 'preserve-3d',
                  animation: reduceMotion ? undefined : 'nk-chat-counter-orbit 6s linear infinite',
                }}
              >
                <svg viewBox="0 0 34 34" width={26} height={26} className="absolute inset-0 drop-shadow-[0_0_8px_rgba(237,28,36,0.6)]">
                  <g fill="#ED1C24">
                    {[0, 72, 144, 216, 288].map((rot) => (
                      <ellipse key={rot} cx="17" cy="8.5" rx="6.1" ry="8.5" transform={`rotate(${rot} 17 17)`} />
                    ))}
                  </g>
                  <circle cx="17" cy="17" r="2.8" fill="#C4141A" />
                  <line x1="17" y1="17" x2="25.5" y2="4.5" stroke="#C4141A" strokeWidth="1.3" strokeLinecap="round" />
                  <circle cx="25.5" cy="4.5" r="1.6" fill="#FFCC00" />
                </svg>
              </div>
            </div>
          </div>
        </div>
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
          {/* Same double-border "stamp" language CitationChip uses for real
              citations — these are the product's actual sources, so they
              carry the citation vocabulary rather than a generic pill. */}
          <span className="inline-flex items-center whitespace-nowrap rounded-md border-2 border-double border-nk-official/50 bg-nk-official/5 px-2.5 py-1 text-xs sm:px-3 sm:py-1.5 sm:text-sm font-mono font-semibold uppercase tracking-tight text-nk-official-dim backdrop-blur-sm dark:border-nk-official/40 dark:bg-nk-official/10 dark:text-nk-official">
            {agency}
          </span>
        </div>
      ))}

      <style>{`
        @keyframes nk-chat-sway { 0%, 100% { transform: rotateY(-17deg); } 50% { transform: rotateY(17deg); } }
        @keyframes nk-chat-bob {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          50% { transform: translateY(-9px) rotate(2.5deg); }
        }
        @keyframes nk-chat-orbit { from { transform: rotateY(0deg); } to { transform: rotateY(360deg); } }
        @keyframes nk-chat-counter-orbit { from { transform: translateZ(40px) rotateY(0deg); } to { transform: translateZ(40px) rotateY(-360deg); } }
        @keyframes nk-chat-dot { 0%, 60%, 100% { transform: translateY(0); opacity: 0.35; } 30% { transform: translateY(-5px); opacity: 1; } }
      `}</style>
    </div>
  );
}
