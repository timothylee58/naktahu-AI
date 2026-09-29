import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EXPO_IN, EXPO_OUT, IN_OUT, clamp, display, mono } from "../Promo/theme";

/**
 * Walkthrough engine: a 1920x1080 "app space" filmed by a virtual camera.
 * Everything a viewer tracks (cursor, callouts, focus ring) lives in app space
 * so it stays glued to the UI through every pan and zoom.
 *
 * 90 BPM at 30fps: one beat is exactly 20 frames, one bar 80. A 100s cut is
 * 3000 frames = 37.5 bars; every chapter is 6 bars, so chapter cuts land on
 * the downbeat and camera moves are timed to beats.
 */
export const BEAT = 20;
export const BAR = 80;
export const TOTAL = 3000;
export const APP_W = 1920;
export const APP_H = 1080;

export const beatPulse = (frame: number) => Math.exp(-(frame % BEAT) / 3.4);

export const prog = (frame: number, start: number, dur: number, easing = EXPO_OUT) =>
  interpolate(frame, [start, start + dur], [0, 1], { ...clamp, easing });

// ---------------------------------------------------------------- camera
/** A camera key: at frame `f`, centre app-space point (x, y) at zoom `z` (1 = whole app). */
export type CamKey = { f: number; x: number; y: number; z: number; tilt?: number };

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** Hold between keys, ease-in-out across each move; a move takes `move` frames ending on the key. */
export const camAt = (keys: CamKey[], frame: number, move = 24): Required<CamKey> => {
  const full = (k: CamKey): Required<CamKey> => ({ tilt: 0, ...k });
  if (frame <= keys[0].f) return full(keys[0]);
  for (let i = 1; i < keys.length; i++) {
    const a = full(keys[i - 1]);
    const b = full(keys[i]);
    if (frame <= b.f) {
      const span = Math.min(move, b.f - a.f);
      const t = interpolate(frame, [b.f - span, b.f], [0, 1], { ...clamp, easing: IN_OUT });
      // zoom interpolates in log space so zooming in and out feel symmetric
      return { f: frame, x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t), z: Math.exp(lerp(Math.log(a.z), Math.log(b.z), t)), tilt: lerp(a.tilt, b.tilt, t) };
    }
  }
  return full(keys[keys.length - 1]);
};

export const CamContext = React.createContext<{ scale: number }>({ scale: 1 });

/**
 * Films app space. At z=1 the whole app fits with a cinematic margin; the
 * slight perspective tilt at wide shots flattens out as the camera pushes in.
 */
export const Camera: React.FC<{ keys: CamKey[]; move?: number; children: React.ReactNode }> = ({ keys, move, children }) => {
  const frame = useCurrentFrame();
  const { width: W, height: H } = useVideoConfig();
  const cam = camAt(keys, frame, move);
  const fit = Math.min(W / APP_W, H / APP_H) * 0.86;
  const scale = fit * cam.z;
  // tiny drift so a held shot never looks frozen
  const dx = Math.sin(frame / 47) * 3;
  const dy = Math.cos(frame / 53) * 2;
  const wide = interpolate(cam.z, [1, 1.6], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ perspective: 2400, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: APP_W,
          height: APP_H,
          transformOrigin: "0 0",
          transform: `translate(${W / 2 + dx}px, ${H / 2 + dy}px) rotateX(${(cam.tilt + 4) * wide}deg) scale(${scale}) translate(${-cam.x}px, ${-cam.y}px)`,
        }}
      >
        <CamContext.Provider value={{ scale }}>{children}</CamContext.Provider>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- cursor
export type CurKey = { f: number; x: number; y: number; click?: boolean; hide?: boolean };

const curPos = (keys: CurKey[], frame: number) => {
  if (frame <= keys[0].f) return keys[0];
  for (let i = 1; i < keys.length; i++) {
    const a = keys[i - 1];
    const b = keys[i];
    if (frame <= b.f) {
      const span = Math.min(18, b.f - a.f);
      const t = interpolate(frame, [b.f - span, b.f], [0, 1], { ...clamp, easing: IN_OUT });
      // a slight arc, the way a hand actually moves a mouse
      const arc = Math.sin(t * Math.PI) * Math.min(60, Math.hypot(b.x - a.x, b.y - a.y) * 0.08);
      return { ...b, x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) - arc };
    }
  }
  return keys[keys.length - 1];
};

/** Mouse cursor in app space, counter-scaled to a constant on-screen size, with click ripples. */
export const Cursor: React.FC<{ keys: CurKey[] }> = ({ keys }) => {
  const frame = useCurrentFrame();
  const { scale } = React.useContext(CamContext);
  const p = curPos(keys, frame);
  const clicks = keys.filter((k) => k.click && frame >= k.f && frame < k.f + 22);
  const pressing = keys.some((k) => k.click && frame >= k.f - 2 && frame < k.f + 4);
  const first = keys[0].f;
  const vis = prog(frame, first, 8) * (keys.some((k) => k.hide && frame >= k.f) ? 0 : 1);
  const s = 1 / scale;
  return (
    <>
      {clicks.map((k) => {
        const t = (frame - k.f) / 22;
        return (
          <div
            key={k.f}
            style={{
              position: "absolute",
              left: k.x,
              top: k.y,
              width: 90 * s,
              height: 90 * s,
              translate: "-50% -50%",
              borderRadius: "50%",
              border: `${3 * s}px solid ${C.blueHi}`,
              scale: `${0.2 + t * 1.2}`,
              opacity: 1 - t,
              pointerEvents: "none",
            }}
          />
        );
      })}
      <svg
        width={40 * s}
        height={40 * s}
        viewBox="0 0 40 40"
        style={{ position: "absolute", left: p.x, top: p.y, translate: `${-4 * s}px ${-3 * s}px`, opacity: vis, scale: pressing ? "0.86" : "1", transformOrigin: "10% 10%", filter: "drop-shadow(0 6px 10px rgba(0,0,0,0.45))", overflow: "visible" }}
      >
        <path d="M5 3 L5 31 L12.5 24.5 L17.5 36 L22.5 33.8 L17.6 22.6 L27.5 22.2 Z" fill="white" stroke="#0B1030" strokeWidth="2.2" strokeLinejoin="round" />
      </svg>
    </>
  );
};

// ---------------------------------------------------------------- focus + callouts
/** Soft spotlight: dims everything in app space except one rect. */
export const Spotlight: React.FC<{ x: number; y: number; w: number; h: number; from: number; to: number; r?: number }> = ({ x, y, w, h, from, to, r = 24 }) => {
  const frame = useCurrentFrame();
  const o = Math.min(prog(frame, from, 12), 1 - prog(frame, to - 10, 10, EXPO_IN));
  if (o <= 0) return null;
  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", opacity: o }}>
      <div
        style={{
          position: "absolute",
          left: x - 10,
          top: y - 10,
          width: w + 20,
          height: h + 20,
          borderRadius: r,
          boxShadow: `0 0 0 4000px rgba(3,5,18,0.62), 0 0 0 3px ${C.blueHi}, 0 0 60px rgba(123,145,255,0.55)`,
        }}
      />
    </div>
  );
};

/** Label with a leader line pointing at an app-space point. Counter-scaled so it reads at any zoom. */
export const Callout: React.FC<{ x: number; y: number; text: string; from: number; to: number; side?: "left" | "right" | "top" | "bottom"; color?: string }> = ({
  x,
  y,
  text,
  from,
  to,
  side = "right",
  color = C.amber,
}) => {
  const frame = useCurrentFrame();
  const { scale } = React.useContext(CamContext);
  const s = 1 / scale;
  const inP = prog(frame, from, 14);
  const outP = prog(frame, to - 8, 8, EXPO_IN);
  if (inP <= 0 || outP >= 1) return null;
  const len = 70 * s * inP;
  const dir = { right: [1, 0], left: [-1, 0], top: [0, -1], bottom: [0, 1] }[side];
  const ex = x + dir[0] * len;
  const ey = y + dir[1] * len;
  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", opacity: 1 - outP }}>
      <svg style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }} width={1} height={1}>
        <line x1={x} y1={y} x2={ex} y2={ey} stroke={color} strokeWidth={3 * s} strokeLinecap="round" />
        <circle cx={x} cy={y} r={7 * s * inP} fill={color} />
        <circle cx={x} cy={y} r={7 * s + 16 * s * ((frame - from) % 30) / 30} fill="none" stroke={color} strokeWidth={2 * s} opacity={1 - ((frame - from) % 30) / 30} />
      </svg>
      <div
        style={{
          position: "absolute",
          left: ex,
          top: ey,
          translate: side === "right" ? `${10 * s}px -50%` : side === "left" ? `calc(-100% - ${10 * s}px) -50%` : side === "top" ? `-50% calc(-100% - ${10 * s}px)` : `-50% ${10 * s}px`,
          fontFamily: display,
          fontSize: 28 * s,
          fontWeight: 700,
          color: "#1A1204",
          background: color,
          padding: `${10 * s}px ${20 * s}px`,
          borderRadius: 14 * s,
          whiteSpace: "nowrap",
          boxShadow: `0 ${10 * s}px ${30 * s}px rgba(0,0,0,0.4)`,
          opacity: inP,
          scale: `${0.8 + 0.2 * inP}`,
        }}
      >
        {text}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- text helpers
/** Characters of `text` typed so far: ~1 char per `fpc` frames starting at `start`. */
export const typed = (text: string, frame: number, start: number, fpc = 1.1) =>
  text.slice(0, Math.max(0, Math.floor((frame - start) / fpc)));

/** Word-streamed text, the way the answer engine renders tokens as they arrive. */
export const streamed = (text: string, frame: number, start: number, wordsPerFrame = 0.9) => {
  const words = text.split(" ");
  const n = Math.max(0, Math.floor((frame - start) * wordsPerFrame));
  return words.slice(0, n).join(" ");
};

export const Caret: React.FC<{ on?: boolean; h?: number }> = ({ on = true, h = 30 }) => {
  const frame = useCurrentFrame();
  if (!on) return null;
  return <span style={{ display: "inline-block", width: 3, height: h, marginLeft: 2, background: C.blueHi, verticalAlign: "middle", opacity: Math.floor(frame / 8) % 2 ? 0 : 1 }} />;
};

// ---------------------------------------------------------------- screen-space overlays
/**
 * Narration caption — there is no voice-over, so the story is told in two
 * lines at the lower left: a short line in white, an optional detail in muted.
 */
export const Caption: React.FC<{ from: number; to: number; text: string; detail?: string }> = ({ from, to, text, detail }) => {
  const frame = useCurrentFrame();
  const { height: H } = useVideoConfig();
  const inP = prog(frame, from, 14);
  const outP = prog(frame, to - 8, 8, EXPO_IN);
  if (inP <= 0 || outP >= 1) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: 64,
        bottom: 64,
        maxWidth: 1100,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "22px 32px 24px",
        borderRadius: 24,
        background: "rgba(8,11,34,0.78)",
        backdropFilter: "blur(18px)",
        border: `1.5px solid ${C.line}`,
        boxShadow: "0 30px 80px rgba(0,0,0,0.45)",
        opacity: inP * (1 - outP),
        translate: `${(1 - inP) * -40 + outP * -30}px ${H * 0}px`,
        filter: `blur(${(1 - inP) * 6 + outP * 6}px)`,
      }}
    >
      <div style={{ fontFamily: display, fontSize: 40, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.15, color: C.white }}>{text}</div>
      {detail && <div style={{ fontFamily: display, fontSize: 27, fontWeight: 500, lineHeight: 1.35, color: C.mute }}>{detail}</div>}
    </div>
  );
};

/** Chapter HUD: brand at top-left, "02 / 05  Chapter name" top-right, segmented progress along the bottom. */
export const Hud: React.FC<{ chapters: { name: string; from: number; to: number }[]; show: [number, number]; series: string }> = ({ chapters, show, series }) => {
  const frame = useCurrentFrame();
  const { width: W, height: H } = useVideoConfig();
  const vis = Math.min(prog(frame, show[0], 12), 1 - prog(frame, show[1] - 10, 10, EXPO_IN));
  if (vis <= 0) return null;
  const idx = chapters.findIndex((c) => frame >= c.from && frame < c.to);
  const x0 = 64;
  const x1 = W - 64;
  const seg = (x1 - x0 - (chapters.length - 1) * 10) / chapters.length;
  const cur = chapters[idx];
  return (
    <AbsoluteFill style={{ opacity: vis, pointerEvents: "none" }}>
      <div style={{ position: "absolute", left: x0, top: 44, fontFamily: mono, fontSize: 22, letterSpacing: "0.2em", color: C.mute }}>
        NAKTAHU.MY <span style={{ color: C.amber }}>·</span> {series}
      </div>
      {cur && (
        <div key={idx} style={{ position: "absolute", right: W - x1, top: 38, display: "flex", alignItems: "baseline", gap: 14, fontFamily: display }}>
          <span style={{ fontFamily: mono, fontSize: 26, color: C.amber }}>{String(idx + 1).padStart(2, "0")}</span>
          <span style={{ fontFamily: mono, fontSize: 22, color: C.mute }}>/ {String(chapters.length).padStart(2, "0")}</span>
          <span style={{ fontSize: 28, fontWeight: 700, color: C.white, opacity: prog(frame, cur.from, 12), translate: `${(1 - prog(frame, cur.from, 12)) * 20}px 0` }}>{cur.name}</span>
        </div>
      )}
      <div style={{ position: "absolute", left: x0, top: H - 22, display: "flex", gap: 10 }}>
        {chapters.map((c, i) => {
          const fill = interpolate(frame, [c.from, c.to], [0, 1], clamp);
          return (
            <div key={c.name} style={{ width: seg, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.12)", overflow: "hidden" }}>
              <div style={{ width: `${fill * 100}%`, height: 5, background: i === idx ? C.amber : C.blueHi }} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/**
 * Chapter interstitial: the number slams in on the downbeat, the title wipes
 * across, and it all clears by beat 3 while the camera is already moving.
 */
export const ChapterCard: React.FC<{ n: number; title: string; line: string }> = ({ n, title, line }) => {
  const frame = useCurrentFrame();
  const out = prog(frame, BEAT * 2 + 6, 12, EXPO_IN);
  if (out >= 1) return null;
  const numP = prog(frame, 0, 10);
  const wipe = prog(frame, 4, 16);
  const lineP = prog(frame, 12, 14);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", pointerEvents: "none" }}>
      <AbsoluteFill style={{ background: "rgba(4,6,20,0.72)", backdropFilter: `blur(${14 * (1 - out)}px)`, opacity: (1 - out) * Math.min(1, frame / 4) }} />
      <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 48, opacity: 1 - out, translate: `${out * -120}px 0`, filter: `blur(${out * 10}px)` }}>
        <div style={{ fontFamily: display, fontSize: 260, fontWeight: 800, letterSpacing: "-0.06em", lineHeight: 0.9, color: "transparent", WebkitTextStroke: `3px ${C.blueHi}`, opacity: numP, scale: `${1.4 - 0.4 * numP}` }}>
          {String(n).padStart(2, "0")}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ overflow: "hidden" }}>
            <div style={{ fontFamily: display, fontSize: 110, fontWeight: 800, letterSpacing: "-0.045em", lineHeight: 1, color: C.white, clipPath: `inset(0 ${(1 - wipe) * 100}% 0 0)` }}>{title}</div>
          </div>
          <div style={{ fontFamily: display, fontSize: 40, fontWeight: 500, color: C.mute, opacity: lineP, translate: `0 ${(1 - lineP) * 14}px` }}>{line}</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Beat-reactive backdrop behind the filmed app. */
export const Backdrop: React.FC<{ hue?: [string, string]; drums: (f: number) => boolean }> = ({ hue = ["59,91,255", "120,70,255"], drums }) => {
  const frame = useCurrentFrame();
  const t = frame / 30;
  const k = drums(frame) ? beatPulse(frame) : 0;
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, overflow: "hidden" }}>
      <AbsoluteFill style={{ background: `radial-gradient(1100px 900px at ${30 + Math.sin(t * 0.3) * 14}% ${28 + Math.cos(t * 0.25) * 10}%, rgba(${hue[0]},${0.3 + k * 0.08}), transparent 70%)` }} />
      <AbsoluteFill style={{ background: `radial-gradient(900px 800px at ${75 + Math.cos(t * 0.22) * 12}% ${72 + Math.sin(t * 0.3) * 10}%, rgba(${hue[1]},${0.18 + k * 0.05}), transparent 70%)` }} />
      <AbsoluteFill
        style={{
          backgroundImage: "radial-gradient(rgba(170,185,255,0.16) 1.3px, transparent 1.5px)",
          backgroundSize: "46px 46px",
          backgroundPosition: `${(frame * 0.4) % 46}px ${(frame * 0.25) % 46}px`,
          maskImage: "radial-gradient(ellipse 80% 70% at 50% 50%, black 10%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse 80% 70% at 50% 50%, black 10%, transparent 80%)",
          opacity: 0.6 + k * 0.4,
        }}
      />
    </AbsoluteFill>
  );
};

export { C, display, mono, clamp, EXPO_IN, EXPO_OUT, IN_OUT };
