import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EXPO_IN, EXPO_OUT, clamp, display, mono } from "./theme";

/** The persistent stage every scene plays on: drifting light, dot grid, grain, vignette. */
export const Stage: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = frame / 30;
  const endGlow = interpolate(frame, [durationInFrames - 90, durationInFrames - 30], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(900px 700px at ${760 + Math.sin(t * 0.5) * 220}px ${380 + Math.cos(t * 0.4) * 140}px, rgba(59,91,255,${0.28 + endGlow * 0.12}), transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(760px 620px at ${1380 + Math.cos(t * 0.35) * 200}px ${700 + Math.sin(t * 0.45) * 120}px, rgba(110,70,255,0.18), transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(520px 420px at ${1500 + Math.sin(t * 0.6) * 120}px ${240 + Math.cos(t * 0.5) * 80}px, rgba(255,178,56,${0.07 + endGlow * 0.05}), transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage: "radial-gradient(rgba(170,185,255,0.16) 1.2px, transparent 1.4px)",
          backgroundSize: "44px 44px",
          backgroundPosition: `${(frame * 0.35) % 44}px ${(frame * 0.2) % 44}px`,
          maskImage: "radial-gradient(ellipse 70% 60% at 50% 50%, black 20%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse 70% 60% at 50% 50%, black 20%, transparent 80%)",
        }}
      />
    </AbsoluteFill>
  );
};

export const Finish: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse 85% 80% at 50% 50%, transparent 55%, rgba(2,3,12,0.75) 100%)" }} />
      <svg width="100%" height="100%" style={{ position: "absolute", opacity: 0.07, mixBlendMode: "overlay" }}>
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={Math.floor(frame / 2) % 50} stitchTiles="stitch" />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
    </AbsoluteFill>
  );
};

/** Word-by-word masked rise, with an optional matching exit. */
export const Stagger: React.FC<{
  text: string;
  frame: number;
  start: number;
  end?: number;
  step?: number;
  style?: React.CSSProperties;
  accent?: Record<string, string>;
}> = ({ text, frame, start, end, step = 3, style, accent = {} }) => {
  const words = text.split(" ");
  return (
    <div style={{ fontFamily: display, display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: "0.26em", ...style }}>
      {words.map((w, i) => {
        const inP = interpolate(frame, [start + i * step, start + i * step + 16], [0, 1], { ...clamp, easing: EXPO_OUT });
        const outP = end === undefined ? 0 : interpolate(frame, [end + i * 1.5, end + i * 1.5 + 10], [0, 1], { ...clamp, easing: EXPO_IN });
        return (
          <span key={i} style={{ display: "inline-block", overflow: "hidden", paddingBottom: "0.12em", marginBottom: "-0.12em" }}>
            <span
              style={{
                display: "inline-block",
                translate: `0 ${(1 - inP) * 105 - outP * 105}%`,
                rotate: `${(1 - inP) * 6}deg`,
                filter: `blur(${(1 - inP) * 8 + outP * 8}px)`,
                opacity: inP * (1 - outP),
                color: accent[w] ?? undefined,
              }}
            >
              {w}
            </span>
          </span>
        );
      })}
    </div>
  );
};

export const Eyebrow: React.FC<{ children: React.ReactNode; frame: number; start: number; color?: string }> = ({
  children,
  frame,
  start,
  color = C.amber,
}) => {
  const p = interpolate(frame, [start, start + 14], [0, 1], { ...clamp, easing: EXPO_OUT });
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, opacity: p, translate: `${(1 - p) * -20}px 0` }}>
      <div style={{ width: 36 * p, height: 2, background: color }} />
      <div style={{ fontFamily: mono, fontSize: 24, letterSpacing: "0.18em", color, fontWeight: 500 }}>{children}</div>
    </div>
  );
};
