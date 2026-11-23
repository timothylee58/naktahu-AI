'use client';

import { useRef, type ReactNode } from 'react';
import { motion, useMotionValue, useReducedMotion, useSpring, useTransform } from 'framer-motion';

interface TiltCardProps {
  children: ReactNode;
  className?: string;
  /** Max rotation in degrees at the card's edge. Small on purpose — this is
   * a "the card is a physical object" cue, not a flip animation. */
  maxTilt?: number;
}

/**
 * Cursor-follow 3D tilt, restrained: rotateX/rotateY track pointer position
 * within the card (via a CSS perspective on the wrapper), springed so the
 * card settles instead of snapping, and reset on pointer leave. Mouse/pen
 * only — touch has no hover, so a touch "tilt" would just stick crooked
 * after the last tap, which reads as broken rather than tactile.
 *
 * No effect under prefers-reduced-motion: this is a pure decoration,
 * disabling it costs nothing functionally, and a 3D-tilt card is exactly
 * the kind of motion that guidance asks to skip.
 */
export function TiltCard({ children, className, maxTilt = 6 }: TiltCardProps) {
  const reduceMotion = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const spring = { stiffness: 300, damping: 24, mass: 0.6 };
  const sx = useSpring(px, spring);
  const sy = useSpring(py, spring);
  const rotateX = useTransform(sy, [0, 1], [maxTilt, -maxTilt]);
  const rotateY = useTransform(sx, [0, 1], [-maxTilt, maxTilt]);

  if (reduceMotion) {
    return <div className={className}>{children}</div>;
  }

  const handleMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== 'mouse' && e.pointerType !== 'pen') return;
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    px.set((e.clientX - rect.left) / rect.width);
    py.set((e.clientY - rect.top) / rect.height);
  };
  const reset = () => {
    px.set(0.5);
    py.set(0.5);
  };

  return (
    <div ref={ref} style={{ perspective: 800 }} onPointerMove={handleMove} onPointerLeave={reset}>
      <motion.div
        style={{ rotateX, rotateY, transformStyle: 'preserve-3d' }}
        className={className}
      >
        {children}
      </motion.div>
    </div>
  );
}
