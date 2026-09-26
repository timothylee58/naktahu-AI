import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EXPO_IN, EXPO_OUT, clamp, display, mono } from "../Promo/theme";
import { useLang } from "./i18n";

/** 128.57 BPM at 30fps: one beat is exactly 14 frames, one bar 56. */
export const BEAT = 14;
export const BAR = 56;
export const STEP = BEAT / 4;
export const TOTAL = 1140;

export type Layout = {
  W: number;
  H: number;
  v: boolean;
  /** where the 960x800 hero-UI mock is placed */
  mock: { x: number; y: number; scale: number };
  text: { x: number; w: number };
  headline: number;
};

export const useLayout = (): Layout => {
  const { width: W, height: H } = useVideoConfig();
  const v = H > W;
  return v
    ? { W, H, v, mock: { x: 60, y: 720, scale: 1 }, text: { x: 80, w: 920 }, headline: 92 }
    : { W, H, v, mock: { x: 900, y: 140, scale: 1 }, text: { x: 110, w: 750 }, headline: 80 };
};

/** Kick-drum pulse: 1 on every beat, decaying before the next. */
export const beatPulse = (frame: number) => Math.exp(-(frame % BEAT) / 3.2);

/** 0..1 progress of an animation that starts at `start` and lasts `dur` frames. */
export const prog = (frame: number, start: number, dur: number, easing = EXPO_OUT) =>
  interpolate(frame, [start, start + dur], [0, 1], { ...clamp, easing });

/** Punch in on the downbeat, whip out just before the next one. */
export const SceneFrame: React.FC<{ dur?: number; dir?: 1 | -1; children: React.ReactNode }> = ({
  dur = BAR,
  dir = 1,
  children,
}) => {
  const frame = useCurrentFrame();
  const inP = prog(frame, 0, 7);
  const outP = interpolate(frame, [dur - 5, dur], [0, 1], { ...clamp, easing: EXPO_IN });
  const bump = 0.006 * beatPulse(frame);
  return (
    <AbsoluteFill
      style={{
        scale: `${(1.1 - 0.1 * inP) * (1 + frame * 0.0004 + bump)}`,
        translate: `${outP * -140 * dir}px ${(1 - inP) * 0}px`,
        opacity: Math.min(1, inP * 1.6) * (1 - outP),
        filter: `blur(${(1 - inP) * 12 + outP * 16}px)`,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

/** Big BM headline: one line per beat-chunk, each line slamming in on its beat. */
export const Slam: React.FC<{
  chunks: string[];
  size: number;
  at?: number[];
  accent?: number[];
  align?: "left" | "center";
  color?: string;
  /** keep every chunk on one wrapping row instead of one line per beat */
  inline?: boolean;
}> = ({ chunks, size, at, accent = [], align = "left", color = C.white, inline = false }) => {
  const frame = useCurrentFrame();
  // Han glyphs are full-width already: negative tracking that tightens Latin display type crushes them.
  const cjk = useLang() === "zh";
  const center = align === "center";
  const item = (i: number) => {
    const p = prog(frame, at?.[i] ?? i * 3, 9);
    return (
      <div
        key={i}
        style={{
          fontFamily: display,
          fontSize: size,
          fontWeight: 800,
          letterSpacing: cjk ? "0.01em" : "-0.04em",
          lineHeight: cjk ? 1.2 : 1.04,
          color: accent.includes(i) ? C.blueHi : color,
          textAlign: align,
          opacity: p,
          scale: `${1.22 - 0.22 * p}`,
          transformOrigin: center ? "50% 60%" : "0% 60%",
          translate: `0 ${(1 - p) * 30}px`,
          filter: `blur(${(1 - p) * 10}px)`,
        }}
      >
        {chunks[i]}
      </div>
    );
  };
  return inline ? (
    <div style={{ display: "flex", flexWrap: "wrap", columnGap: size * 0.26, justifyContent: center ? "center" : "flex-start" }}>{chunks.map((_, i) => item(i))}</div>
  ) : (
    <div style={{ display: "flex", flexDirection: "column", alignItems: center ? "center" : "flex-start" }}>{chunks.map((_, i) => item(i))}</div>
  );
};

export const Kicker: React.FC<{ children: React.ReactNode; color?: string }> = ({ children, color = C.amber }) => {
  const frame = useCurrentFrame();
  const p = prog(frame, 0, 10);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, opacity: p }}>
      <div style={{ width: 40 * p, height: 3, borderRadius: 2, background: color }} />
      <div style={{ fontFamily: mono, fontSize: 26, fontWeight: 500, letterSpacing: "0.2em", color }}>{children}</div>
    </div>
  );
};

/** Standard feature layout: kicker + slam headline + sub, with the hero-UI mock beside/below. */
export const Feature: React.FC<{
  kicker: string;
  chunks: string[];
  at?: number[];
  accent?: number[];
  sub?: string;
  dir?: 1 | -1;
  inline?: boolean;
  children: React.ReactNode;
}> = ({ kicker, chunks, at, accent, sub, dir = 1, inline = false, children }) => {
  const L = useLayout();
  const frame = useCurrentFrame();
  const subP = prog(frame, 10, 12);
  const mockP = prog(frame, 2, 14);
  return (
    <SceneFrame dir={dir}>
      <div
        style={{
          position: "absolute",
          left: L.text.x,
          top: L.v ? 250 : 0,
          width: L.text.w,
          height: L.v ? L.mock.y - 40 - 250 : L.H,
          display: "flex",
          flexDirection: "column",
          justifyContent: L.v ? "flex-end" : "center",
          gap: L.v ? 20 : 26,
        }}
      >
        <Kicker>{kicker}</Kicker>
        <Slam chunks={chunks} at={at} accent={accent} size={L.headline} inline={inline} />
        {sub && (
          <div style={{ fontFamily: display, fontSize: L.v ? 44 : 38, lineHeight: 1.3, color: C.mute, opacity: subP, translate: `0 ${(1 - subP) * 16}px` }}>
            {sub}
          </div>
        )}
      </div>
      <div
        style={{
          position: "absolute",
          left: L.mock.x,
          top: L.mock.y,
          width: 960,
          height: 800,
          scale: `${L.mock.scale * (0.92 + 0.08 * mockP)}`,
          transformOrigin: "50% 50%",
          opacity: mockP,
          translate: L.v ? `0 ${(1 - mockP) * 80}px` : `${(1 - mockP) * 120}px 0`,
        }}
      >
        {children}
      </div>
    </SceneFrame>
  );
};

/** App window chrome used by every mock. */
export const Window: React.FC<{ path: string; children: React.ReactNode; tilt?: boolean }> = ({ path, children }) => {
  return (
    <div
      style={{
        width: 960,
        height: 800,
        borderRadius: 36,
        background: "linear-gradient(165deg, rgba(24,31,78,0.97), rgba(10,14,40,0.98))",
        border: "1.5px solid rgba(140,160,255,0.26)",
        boxShadow: "0 50px 120px rgba(0,0,0,0.55), 0 0 110px rgba(59,91,255,0.2)",
        overflow: "hidden",
        position: "relative",
        fontFamily: display,
        color: C.white,
      }}
    >
      <div style={{ height: 74, display: "flex", alignItems: "center", gap: 12, padding: "0 30px", borderBottom: `1px solid ${C.line}` }}>
        {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
          <div key={c} style={{ width: 15, height: 15, borderRadius: 8, background: c, opacity: 0.85 }} />
        ))}
        <div style={{ marginLeft: 22, flex: 1, height: 44, borderRadius: 14, background: "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", padding: "0 20px", gap: 12 }}>
          <svg width="16" height="18" viewBox="0 0 16 18">
            <rect x="1" y="8" width="14" height="10" rx="2" fill={C.mute} />
            <path d="M4 8 V5 a4 4 0 0 1 8 0 V8" stroke={C.mute} strokeWidth="2" fill="none" />
          </svg>
          <span style={{ fontFamily: mono, fontSize: 24, color: C.mute }}>naktahu.my{path}</span>
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 74, bottom: 0, padding: 36 }}>{children}</div>
    </div>
  );
};

export const Pill: React.FC<{ children: React.ReactNode; bg?: string; border?: string; color?: string; size?: number; style?: React.CSSProperties }> = ({
  children,
  bg = "rgba(59,91,255,0.16)",
  border = "rgba(123,145,255,0.45)",
  color = C.white,
  size = 28,
  style,
}) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      padding: `${size * 0.42}px ${size * 0.8}px`,
      borderRadius: 999,
      background: bg,
      border: `1.5px solid ${border}`,
      color,
      fontFamily: display,
      fontSize: size,
      fontWeight: 700,
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    {children}
  </div>
);

/** Spring-ish pop for UI elements landing on a beat. */
export const pop = (frame: number, at: number) => {
  const p = prog(frame, at, 10, EXPO_OUT);
  return { opacity: Math.min(1, p * 2), scale: `${0.6 + 0.4 * p + Math.sin(p * Math.PI) * 0.08}` };
};

export { C, display, mono, clamp, EXPO_IN, EXPO_OUT };
