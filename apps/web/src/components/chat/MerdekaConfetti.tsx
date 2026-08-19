'use client';

import { CSSProperties, useEffect, useState } from 'react';

// React's CSSProperties doesn't include CSS custom properties by name —
// this narrow extension avoids the `as any` cast for the handful this
// component sets per-particle.
interface ParticleStyle extends CSSProperties {
  '--mc-left': string;
  '--mc-drift': string;
  '--mc-delay': string;
  '--mc-duration': string;
  '--mc-rotate': string;
}

// One-shot particle burst — triggered when a submitted query mentions
// Merdeka/Hari Malaysia (see chat/page.tsx's KEMERDEKAAN_KEYWORDS check),
// never on a timer or on page load. Geometric sparks (small rotated
// rects/diamonds in the four Jalur Gemilang colours), not a confetti-image
// library — plays once and unmounts itself, honouring
// prefers-reduced-motion by simply not rendering (a burst IS the motion;
// there's no static equivalent worth freezing to).
const COLORS = ['#b3282d', '#ffffff', '#ffcc00', '#010066'];
const PARTICLE_COUNT = 18;

interface Particle {
  id: number;
  left: number; // vw offset from center, %
  delay: number; // s
  duration: number; // s
  color: string;
  rotate: number;
  drift: number; // vw
}

function buildParticles(): Particle[] {
  return Array.from({ length: PARTICLE_COUNT }).map((_, i) => ({
    id: i,
    left: Math.random() * 60 - 30,
    delay: Math.random() * 0.15,
    duration: 1.1 + Math.random() * 0.6,
    color: COLORS[i % COLORS.length],
    rotate: Math.random() * 360,
    drift: Math.random() * 40 - 20,
  }));
}

export function MerdekaConfetti({ onDone }: { onDone: () => void }) {
  const [particles] = useState<Particle[]>(buildParticles);
  const [render, setRender] = useState(false);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      onDone();
      return;
    }
    setRender(true);
    const timer = window.setTimeout(onDone, 1900);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!render) return null;

  return (
    <div aria-hidden className="pointer-events-none fixed inset-x-0 top-0 z-50 h-0 overflow-visible">
      {particles.map((p) => (
        <span
          key={p.id}
          className="merdeka-confetti-particle absolute top-0 left-1/2"
          style={{
            '--mc-left': `${p.left}vw`,
            '--mc-drift': `${p.drift}vw`,
            '--mc-delay': `${p.delay}s`,
            '--mc-duration': `${p.duration}s`,
            '--mc-rotate': `${p.rotate}deg`,
            backgroundColor: p.color,
          } as ParticleStyle}
        />
      ))}
    </div>
  );
}
