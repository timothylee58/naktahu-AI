'use client';

import { useEffect, useRef, useState } from 'react';
import { useI18n } from '@/lib/i18n';

// Full-screen transition loader, translated from the "NakTahu Loader" motion
// design (a 3D extruded speech-bubble that spins/bobs, an orbiting official
// badge, a staged status label, and a progress bar) into a real component
// for actual page-navigation transitions — not the design's own infinite
// demo loop, which was tuned for a marketing showcase (4.5s+relooping).
// Here the bar is a short, one-shot ~1.1s cosmetic ramp: it does not gate
// navigation itself (the caller's own router.push timing does that), it
// just fills the transition window with something intentional instead of
// a blank frame. Unmounts naturally once the destination route replaces
// this component — no explicit "hide" step needed.
//
// Scope note (see PR body): wired into the landing page's single real
// navigation CTA (the hero "Mula Bertanya" button — LandingClient.tsx's
// handleStartChat). NOT attached to every clickable element site-wide —
// toggles, modals, and in-place UI changes don't navigate anywhere, and a
// heavy full-screen animation on a theme toggle or a sidebar collapse
// would be a latency regression (Response — kill latency), not a delight.
// Reduced motion: this component has no internal reduced-motion check —
// callers are responsible for never passing show=true under
// prefers-reduced-motion, same as LandingClient's existing reduceMotion
// short-circuit that routes straight to /chat before this would ever
// mount. A "skip straight to navigation" outcome, not a static frame of
// this animation, is what apple-design's reduced-motion guidance (already
// applied throughout this codebase) calls for.
interface PageLoadingScreenProps {
  show: boolean;
  loadSeconds?: number;
  accentColor?: string;
}

const RADIUS = '48% 48% 48% 6px / 52% 52% 52% 6px';
const BUBBLE_DEPTH = 14;

export function PageLoadingScreen({ show, loadSeconds = 1.1, accentColor = '#3B5BFF' }: PageLoadingScreenProps) {
  const { t } = useI18n();
  const [progress, setProgress] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (!show) {
      setProgress(0);
      startRef.current = null;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }
    const duration = loadSeconds * 1000;
    const tick = (t0: number) => {
      if (startRef.current === null) startRef.current = t0;
      const raw = Math.min(1, (t0 - startRef.current) / duration);
      const eased = 1 - Math.pow(1 - raw, 2.2);
      setProgress(Math.round(eased * 100));
      if (raw < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [show, loadSeconds]);

  if (!show) return null;

  const stage = progress < 35 ? 0 : progress < 70 ? 1 : progress < 100 ? 2 : 3;
  const statusLabel = t(`loading_screen.stage${stage + 1}`);

  const layers = Array.from({ length: BUBBLE_DEPTH }, (_, i) => {
    const shade = 0.3 + (i / (BUBBLE_DEPTH - 1)) * 0.42;
    return (
      <div
        key={i}
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: RADIUS,
          background: accentColor,
          filter: `brightness(${shade})`,
          transform: `translateZ(${-i * 2.1}px)`,
        }}
      />
    );
  });

  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col items-center justify-center gap-0 overflow-hidden"
      style={{ background: '#12151C', color: '#EDEAE3', perspective: 1200 }}
      role="status"
      aria-live="polite"
      aria-label={statusLabel}
    >
      {/* Ambient glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[34%] h-[720px] w-[720px] -translate-x-1/2 -translate-y-1/2 rounded-full blur-[10px]"
        style={{
          background: `radial-gradient(closest-side, ${accentColor}33, transparent 72%)`,
          animation: 'nk-loader-glow-pulse 5s ease-in-out infinite',
        }}
      />
      {/* Perspective grid floor */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 bottom-0 h-[420px] w-[1600px] -translate-x-1/2 opacity-[0.16]"
        style={{
          backgroundImage: `linear-gradient(${accentColor} 1px, transparent 1px), linear-gradient(90deg, ${accentColor} 1px, transparent 1px)`,
          backgroundSize: '56px 56px',
          transform: 'perspective(600px) rotateX(72deg)',
          transformOrigin: 'bottom center',
          maskImage: 'linear-gradient(to top, rgba(0,0,0,0.9), transparent 70%)',
          WebkitMaskImage: 'linear-gradient(to top, rgba(0,0,0,0.9), transparent 70%)',
        }}
      />

      <div
        className="relative flex items-center justify-center"
        style={{ width: 260, height: 260, transformStyle: 'preserve-3d' }}
      >
        <div style={{ transformStyle: 'preserve-3d', animation: 'nk-loader-bob 7.5s ease-in-out infinite' }}>
          <div style={{ transformStyle: 'preserve-3d', animation: 'nk-loader-spin-y 9s linear infinite' }}>
            {/* Extruded speech-bubble */}
            <div className="relative" style={{ width: 190, height: 165, transformStyle: 'preserve-3d' }}>
              {layers}
              <div
                className="absolute inset-0 flex items-center justify-center overflow-hidden"
                style={{
                  borderRadius: RADIUS,
                  background: `linear-gradient(150deg, ${accentColor} 0%, #2A45D8 100%)`,
                  boxShadow: `0 0 40px -6px ${accentColor}99, inset 0 2px 0 rgba(255,255,255,0.28)`,
                  transform: 'translateZ(2px)',
                }}
              >
                <div className="flex items-center gap-[11px]" style={{ transform: 'translateY(-6px)' }}>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="inline-block rounded-full bg-white"
                      style={{ width: 15, height: 15, animation: `nk-loader-dot-bounce 1.35s ease-in-out ${i * 0.18}s infinite` }}
                    />
                  ))}
                </div>
                <div
                  aria-hidden
                  className="pointer-events-none absolute inset-0"
                  style={{ background: 'linear-gradient(115deg, rgba(255,255,255,0.30) 0%, rgba(255,255,255,0) 46%)' }}
                />
              </div>
            </div>

            {/* Orbiting "verified" badge */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0"
              style={{ transformStyle: 'preserve-3d', animation: 'nk-loader-orbit 6s linear infinite' }}
            >
              <div
                className="absolute"
                style={{
                  top: 6, left: '50%', marginLeft: 44, width: 34, height: 34,
                  transform: 'translateZ(58px)', transformStyle: 'preserve-3d',
                  animation: 'nk-loader-counter-orbit 6s linear infinite',
                }}
              >
                <div
                  className="absolute inset-0 rounded-full"
                  style={{
                    background: 'radial-gradient(circle at 32% 28%, #FF7A6E 0%, #F0403A 55%, #B21C1C 100%)',
                    boxShadow: '0 0 22px -2px rgba(240,64,58,0.85), inset -3px -4px 8px rgba(0,0,0,0.35)',
                  }}
                />
                <div
                  className="absolute inset-0 rounded-full"
                  style={{ border: '2px solid rgba(240,64,58,0.7)', animation: 'nk-loader-ring-pulse 1.9s ease-out infinite' }}
                />
              </div>
            </div>
          </div>
        </div>

        <div
          aria-hidden
          className="absolute left-1/2 rounded-full"
          style={{
            bottom: -34, width: 190, height: 26, marginLeft: -95,
            background: 'rgba(0,0,0,0.55)', filter: 'blur(14px)',
            animation: 'nk-loader-shadow-breathe 3.6s ease-in-out infinite',
          }}
        />
      </div>

      <div
        className="mt-[74px] text-[40px] font-extrabold leading-none tracking-[-0.035em]"
        style={{ animation: 'nk-loader-rise-in 0.8s cubic-bezier(.16,.84,.44,1) 0.1s backwards' }}
      >
        <span className="text-white">naktahu</span>
        <span style={{ color: accentColor }}>.my</span>
      </div>

      <div
        className="mt-5 h-[18px] whitespace-nowrap text-[12.5px] font-semibold uppercase tracking-[0.14em]"
        style={{ color: '#8A8F98', animation: 'nk-loader-rise-in 0.6s ease 0.2s backwards' }}
      >
        {statusLabel}
      </div>

      <div
        className="mt-[22px] h-[3px] w-60 overflow-hidden rounded-full"
        style={{ background: 'rgba(255,255,255,0.09)', animation: 'nk-loader-rise-in 0.6s ease 0.25s backwards' }}
      >
        <div
          className="h-full w-full origin-left rounded-full"
          style={{
            transform: `scaleX(${progress / 100})`,
            background: `linear-gradient(90deg, ${accentColor}, #7C93FF)`,
            boxShadow: `0 0 12px ${accentColor}`,
            transition: 'transform 0.12s linear',
          }}
        />
      </div>

      <div className="mt-3 font-mono text-xs font-bold tracking-[0.08em]" style={{ color: '#5C616E' }}>
        {progress}%
      </div>

      <style>{`
        @keyframes nk-loader-spin-y { from { transform: rotateY(-24deg); } to { transform: rotateY(336deg); } }
        @keyframes nk-loader-bob {
          0%, 20%, 40%, 60%, 80%, 100% { transform: translate(0, 0) rotate(0deg) scale(0.96); }
          10% { transform: translate(0, -34px) rotate(0deg) scale(1.08); }
          30% { transform: translate(32px, -10px) rotate(13deg) scale(1.08); }
          50% { transform: translate(20px, 28px) rotate(8deg) scale(1.08); }
          70% { transform: translate(-20px, 28px) rotate(-8deg) scale(1.08); }
          90% { transform: translate(-32px, -10px) rotate(-13deg) scale(1.08); }
        }
        @keyframes nk-loader-orbit { from { transform: rotateY(0deg); } to { transform: rotateY(360deg); } }
        @keyframes nk-loader-counter-orbit { from { transform: translateZ(58px) rotateY(0deg); } to { transform: translateZ(58px) rotateY(-360deg); } }
        @keyframes nk-loader-glow-pulse { 0%, 100% { opacity: 0.35; transform: scale(1); } 50% { opacity: 0.65; transform: scale(1.12); } }
        @keyframes nk-loader-ring-pulse { 0% { transform: scale(0.7); opacity: 0.5; } 100% { transform: scale(1.9); opacity: 0; } }
        @keyframes nk-loader-rise-in { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes nk-loader-dot-bounce { 0%, 60%, 100% { transform: translateY(0); opacity: 0.35; } 30% { transform: translateY(-7px); opacity: 1; } }
        @keyframes nk-loader-shadow-breathe { 0%, 100% { transform: scaleX(0.82); opacity: 0.28; } 50% { transform: scaleX(1); opacity: 0.5; } }
      `}</style>
    </div>
  );
}
