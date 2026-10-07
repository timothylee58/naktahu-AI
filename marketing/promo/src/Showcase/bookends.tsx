import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { BAR, BEAT, C, EXPO_IN, EXPO_OUT, Pill, SceneFrame, Slam, clamp, display, mono, pop, prog, useLayout } from "./core";
import { Mark } from "../Promo/Mark";
import { useT } from "./i18n";

/** Bar 0 — the hook, over a live-typing search bar. */
export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const L = useLayout();
  const t = useT();
  const prompt = t("hook.prompt");
  const typed = Math.floor(interpolate(frame, [12, 44], [0, prompt.length], clamp));
  const out = interpolate(frame, [BAR - 5, BAR], [0, 1], { ...clamp, easing: EXPO_IN });
  const size = L.v ? 150 : 150;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: L.v ? 40 : 34, opacity: 1 - out, scale: `${1 + out * 0.2}`, filter: `blur(${out * 12}px)` }}>
      <div style={{ ...pop(frame, 0) }}>
        <Pill size={30} bg="rgba(255,255,255,0.06)" border={C.line}>🇲🇾 {t("hook.badge")}</Pill>
      </div>
      <div style={{ width: L.v ? 940 : 1600 }}>
        <Slam chunks={[t("hook.h0")]} at={[0]} size={size} align="center" />
        <Slam chunks={[t("hook.h1")]} at={[BEAT * 2]} size={size} align="center" accent={[0]} />
      </div>
      <div
        style={{
          width: L.v ? 900 : 1000,
          height: 104,
          borderRadius: 52,
          background: "rgba(255,255,255,0.06)",
          border: "1.5px solid rgba(123,145,255,0.45)",
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "0 16px 0 36px",
          fontFamily: display,
          fontSize: L.v ? 38 : 36,
          color: C.white,
          opacity: prog(frame, 8, 8),
          boxShadow: "0 0 80px rgba(59,91,255,0.25)",
        }}
      >
        <svg width="34" height="34" viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5" stroke={C.mute} strokeWidth="2.2" fill="none" /><path d="M15.5 15.5 L20.5 20.5" stroke={C.mute} strokeWidth="2.2" strokeLinecap="round" /></svg>
        <div style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden" }}>
          {prompt.slice(0, typed)}
          <span style={{ display: "inline-block", width: 3, height: 40, marginLeft: 3, background: C.blueHi, verticalAlign: "middle", opacity: Math.floor(frame / 4) % 2 ? 0 : 1 }} />
        </div>
        <div style={{ width: 76, height: 76, borderRadius: 38, background: C.blue, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg width="32" height="32" viewBox="0 0 28 28"><path d="M14 22 V6 M7 13 L14 6 L21 13" stroke="white" strokeWidth="3.2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const STAGES = ["load.s1", "load.s2", "load.s3", "load.s4"] as const;
const AGENCIES = ["LHDN", "KWSP", "SSM", "PERKESO", "KKM", "JPN"];

/** Bar 1 — the real loading sequence, one stage per beat, riding the riser. */
export const Loading: React.FC = () => {
  const frame = useCurrentFrame();
  const L = useLayout();
  const t = useT();
  const stage = Math.min(3, Math.floor(frame / BEAT));
  const ring = interpolate(frame, [0, BEAT * 3 + 4], [0, 1], { ...clamp, easing: EXPO_OUT });
  const spin = interpolate(frame, [0, BAR], [0, 1], { ...clamp, easing: EXPO_IN }) * 300 + frame * 1.5;
  const suck = interpolate(frame, [BAR - 8, BAR], [0, 1], { ...clamp, easing: EXPO_IN });
  const R = L.v ? 330 : 360;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div style={{ position: "relative", width: 1, height: 1, scale: `${1 - suck * 0.85}`, opacity: 1 - suck * 0.6 }}>
        {AGENCIES.map((a, i) => {
          const ang = ((i * 60 + spin) * Math.PI) / 180;
          const p = prog(frame, i * 2, 10);
          return (
            <div
              key={a}
              style={{
                position: "absolute",
                left: Math.cos(ang) * R * p,
                top: Math.sin(ang) * R * 0.55 * p - 80,
                translate: "-50% -50%",
                opacity: p,
                padding: "14px 26px",
                borderRadius: 999,
                background: "rgba(18,24,64,0.94)",
                border: "1.5px solid rgba(140,160,255,0.4)",
                fontFamily: display,
                fontSize: 30,
                fontWeight: 800,
                color: C.white,
                whiteSpace: "nowrap",
              }}
            >
              {a}
            </div>
          );
        })}
        <svg width="320" height="320" viewBox="0 0 320 320" style={{ position: "absolute", left: -160, top: -240 }}>
          <circle cx="160" cy="160" r="140" stroke="rgba(140,160,255,0.16)" strokeWidth="12" fill="none" />
          <circle cx="160" cy="160" r="140" stroke={stage === 3 ? "#3DDC97" : C.blue} strokeWidth="12" fill="none" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - ring} transform="rotate(-90 160 160)" style={{ filter: `drop-shadow(0 0 14px ${stage === 3 ? "#3DDC97" : C.blue})` }} />
        </svg>
        <div style={{ position: "absolute", left: -95, top: -175 }}>
          <Mark frame={frame} size={190} bubbleAt={0} bloomAt={BEAT * 3} id="load" />
        </div>
        <div style={{ position: "absolute", top: 240, left: 0, translate: "-50% 0", display: "flex", flexDirection: "column", alignItems: "center", gap: 18, width: 1000 }}>
          <div key={stage} style={{ fontFamily: display, fontSize: L.v ? 54 : 50, fontWeight: 800, color: stage === 3 ? "#8FF0C4" : C.white, opacity: prog(frame - stage * BEAT, 0, 5), whiteSpace: "nowrap" }}>
            {t(STAGES[stage])}
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            {STAGES.map((_, i) => (
              <div key={i} style={{ width: 56, height: 8, borderRadius: 4, background: i <= stage ? (stage === 3 ? "#3DDC97" : C.blue) : "rgba(255,255,255,0.12)" }} />
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Bar 2 — the drop: shockwave, mark, wordmark, tagline on the beat. */
export const LogoDrop: React.FC = () => {
  const frame = useCurrentFrame();
  const L = useLayout();
  const t = useT();
  const flash = interpolate(frame, [0, 6], [0.9, 0], clamp);
  const word = "naktahu.my".split("");
  const mark = L.v ? 300 : 250;
  return (
    <SceneFrame>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        {[0, 4, 9].map((d, k) => {
          const p = prog(frame, d, 22);
          return <div key={k} style={{ position: "absolute", width: 2200 * p, height: 2200 * p, borderRadius: 9999, border: `${4 - k}px solid ${k === 1 ? C.amber : C.blueHi}`, opacity: (1 - p) * 0.8 }} />;
        })}
      </AbsoluteFill>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: L.v ? 30 : 40 }}>
        <div style={{ display: "flex", flexDirection: L.v ? "column" : "row", alignItems: "center", gap: L.v ? 24 : 40 }}>
          <div style={{ width: mark, height: mark }}>
            <Mark frame={frame} size={mark} bubbleAt={0} bloomAt={5} id="drop" />
          </div>
          <div style={{ display: "flex", overflow: "hidden", paddingBottom: 16, marginBottom: -16 }}>
            {word.map((ch, i) => {
              const p = prog(frame, 4 + i * 1.2, 12);
              return (
                <span key={i} style={{ display: "inline-block", fontFamily: display, fontWeight: 800, fontSize: L.v ? 170 : 180, letterSpacing: "-0.045em", lineHeight: 1.05, color: i >= 7 ? C.blue : C.white, translate: `0 ${(1 - p) * 110}%`, opacity: p }}>
                  {ch}
                </span>
              );
            })}
          </div>
        </div>
        <Slam chunks={[t("logo.h0"), t("logo.h1")]} at={[BEAT * 2, BEAT * 3]} size={L.v ? 80 : 72} align="center" accent={[1]} inline />
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "white", opacity: flash, mixBlendMode: "screen" }} />
    </SceneFrame>
  );
};

/** Bar 18 — pricing, on the final drop. */
export const PricingMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const card = (at: number, name: string, price: string, note: string, hi: boolean) => (
    <div
      style={{
        ...pop(frame, at),
        height: 370,
        borderRadius: 34,
        padding: "34px 40px",
        background: hi ? "linear-gradient(145deg, #4E6BFF, #2540C9)" : "linear-gradient(165deg, rgba(24,31,78,0.97), rgba(10,14,40,0.98))",
        border: `2px solid ${hi ? "rgba(255,255,255,0.35)" : "rgba(61,220,151,0.55)"}`,
        boxShadow: hi ? "0 30px 80px rgba(59,91,255,0.5)" : "0 30px 70px rgba(0,0,0,0.5)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        fontFamily: display,
        color: "white",
      }}
    >
      <div style={{ fontSize: 40, fontWeight: 800 }}>{name}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <span style={{ fontSize: 120, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1 }}>{price}</span>
        <span style={{ fontSize: 36, fontWeight: 600, opacity: 0.8 }}>{t("price.period")}</span>
      </div>
      <div style={{ fontSize: 30, lineHeight: 1.3, color: hi ? "#E3E8FF" : "#9CF0C8" }}>{note}</div>
    </div>
  );
  return (
    <div style={{ width: 960, height: 800, display: "flex", flexDirection: "column", gap: 40, justifyContent: "center" }}>
      {card(BEAT, t("price.freeName"), "RM 0", t("price.freeNote"), false)}
      {card(BEAT * 2, t("price.proName"), "RM 19", t("price.proNote"), true)}
    </div>
  );
};

/** Bar 19 + tail — the end card on the resolving chord. */
export const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const L = useLayout();
  const t = useT();
  const word = "naktahu.my".split("");
  const shine = interpolate(frame, [26, 46], [-0.3, 1.3], clamp);
  const cta = prog(frame, 16, 12);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", fontFamily: display, gap: 8, translate: L.v ? "0 -80px" : "0 0" }}>
      <div style={{ width: L.v ? 300 : 240, height: L.v ? 300 : 240, marginBottom: 20 }}>
        <Mark frame={frame} size={L.v ? 300 : 240} bubbleAt={0} bloomAt={4} id="end" />
      </div>
      <div style={{ display: "flex", overflow: "hidden", paddingBottom: 14 }}>
        {word.map((ch, i) => {
          const p = prog(frame, 3 + i * 1.3, 14);
          return (
            <span key={i} style={{ display: "inline-block", fontSize: L.v ? 150 : 160, fontWeight: 800, letterSpacing: "-0.045em", lineHeight: 1.05, color: i >= 7 ? C.blue : C.white, translate: `0 ${(1 - p) * 110}%`, opacity: p }}>
              {ch}
            </span>
          );
        })}
      </div>
      <div style={{ fontSize: L.v ? 58 : 56, fontWeight: 600, color: "rgba(244,246,255,0.9)", opacity: prog(frame, 10, 12) }}>{t("end.tagline")}</div>
      <div
        style={{
          position: "relative",
          overflow: "hidden",
          marginTop: 44,
          padding: "28px 60px",
          borderRadius: 999,
          background: `linear-gradient(135deg, #5872FF, ${C.blueDeep})`,
          boxShadow: "0 20px 60px rgba(59,91,255,0.55), inset 0 1.5px 0 rgba(255,255,255,0.3)",
          fontSize: L.v ? 50 : 46,
          fontWeight: 800,
          color: "white",
          opacity: cta,
          scale: `${0.7 + 0.3 * cta}`,
        }}
      >
        {t("end.cta")}
        <div style={{ position: "absolute", top: 0, bottom: 0, left: `${shine * 100}%`, width: 150, translate: "-50% 0", background: "linear-gradient(100deg, transparent, rgba(255,255,255,0.5), transparent)", rotate: "12deg" }} />
      </div>
      <div style={{ position: "absolute", bottom: L.v ? 480 : 60, fontFamily: mono, fontSize: L.v ? 28 : 24, letterSpacing: "0.08em", color: C.mute, opacity: prog(frame, 24, 12) }}>
        {t("end.disclaimer")}
      </div>
    </AbsoluteFill>
  );
};

export { EXPO_OUT };
