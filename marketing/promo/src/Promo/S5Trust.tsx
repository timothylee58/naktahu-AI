import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EXPO_OUT, IN_OUT, clamp, display } from "./theme";
import { Stagger } from "./Shared";

const AGENCIES = ["LHDN", "KWSP", "SSM", "PERKESO", "KKM", "JPN"];
const LANGS = ["Bahasa Malaysia", "English", "中文"];
const HX = 960;
const HY = 560;

export const S5Trust: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const hub = spring({ frame: frame - 4, fps, config: { damping: 12 } });
  const check = interpolate(frame, [14, 30], [0, 1], { ...clamp, easing: EXPO_OUT });

  const nodes = AGENCIES.map((name, i) => {
    const ang = ((i * 60 + 30 + frame * 0.35) * Math.PI) / 180;
    const depth = (Math.sin(ang) + 1) / 2;
    return { name, i, x: HX + Math.cos(ang) * 660, y: HY + Math.sin(ang) * 232, depth };
  });

  const langPos = interpolate(frame, [44, 58, 66, 80], [0, 1, 1, 2], { ...clamp, easing: IN_OUT });

  return (
    <AbsoluteFill style={{ fontFamily: display }}>
      <div style={{ position: "absolute", top: 90, width: "100%" }}>
        <Stagger text="Setiap jawapan, bersumber rasmi." frame={frame} start={2} accent={{ "rasmi.": C.blueHi }} style={{ fontSize: 92, fontWeight: 800, letterSpacing: "-0.04em", color: C.white }} />
      </div>

      <svg width="1920" height="1080" style={{ position: "absolute", inset: 0 }}>
        <ellipse cx={HX} cy={HY} rx={660} ry={232} fill="none" stroke="rgba(140,160,255,0.12)" strokeWidth={1.5} strokeDasharray="4 10" opacity={hub} />
        {nodes.map((n) => {
          const draw = interpolate(frame, [8 + n.i * 3, 24 + n.i * 3], [0, 1], { ...clamp, easing: EXPO_OUT });
          return (
            <line key={n.name} x1={n.x} y1={n.y} x2={n.x + (HX - n.x) * draw} y2={n.y + (HY - n.y) * draw} stroke="url(#lg)" strokeWidth={2} opacity={0.35 + n.depth * 0.45} />
          );
        })}
        {nodes.map((n) =>
          [0, 1].map((k) => {
            const t = ((frame - 24 - n.i * 4 - k * 15) % 30) / 30;
            if (frame - 24 - n.i * 4 - k * 15 < 0) return null;
            return (
              <circle key={`${n.name}${k}`} cx={n.x + (HX - n.x) * t} cy={n.y + (HY - n.y) * t} r={5} fill={C.amber} opacity={Math.sin(t * Math.PI)} style={{ filter: `drop-shadow(0 0 6px ${C.amber})` }} />
            );
          }),
        )}
        <defs>
          <linearGradient id="lg" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor={C.blueHi} />
            <stop offset="1" stopColor={C.blue} />
          </linearGradient>
        </defs>
      </svg>

      <div style={{ position: "absolute", left: HX - 130, top: HY - 130, width: 260, height: 260, scale: `${Math.max(0, hub)}` }}>
        <div style={{ position: "absolute", inset: -26, borderRadius: 999, border: "2px dashed rgba(123,145,255,0.4)", rotate: `${frame * 0.8}deg` }} />
        <div style={{ position: "absolute", inset: 0, borderRadius: 999, background: "radial-gradient(circle at 35% 30%, #6F87FF, #2540C9 70%)", boxShadow: "0 0 90px rgba(59,91,255,0.65), inset 0 2px 0 rgba(255,255,255,0.3)" }} />
        <svg viewBox="0 0 100 100" width={260} height={260} style={{ position: "absolute", inset: 0 }}>
          <path d="M50 22 L72 30 V50 C72 64 62 74 50 79 C38 74 28 64 28 50 V30 Z" fill="rgba(255,255,255,0.14)" stroke="white" strokeWidth="3.5" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - check} />
          <path d="M40 50 L47 57 L61 42" fill="none" stroke="white" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - interpolate(frame, [24, 34], [0, 1], { ...clamp, easing: EXPO_OUT })} />
        </svg>
      </div>

      {nodes.map((n) => {
        const s = spring({ frame: frame - 6 - n.i * 3, fps, config: { damping: 11 } });
        return (
          <div
            key={n.name}
            style={{
              position: "absolute",
              left: n.x,
              top: n.y,
              translate: "-50% -50%",
              scale: `${Math.max(0, s) * (0.78 + n.depth * 0.32)}`,
              opacity: Math.min(1, s * 2) * (0.55 + n.depth * 0.45),
              zIndex: Math.round(n.depth * 10),
              display: "flex",
              alignItems: "center",
              gap: 14,
              padding: "18px 30px",
              borderRadius: 999,
              background: "rgba(18,24,64,0.94)",
              border: "1.5px solid rgba(140,160,255,0.35)",
              boxShadow: "0 18px 40px rgba(0,0,0,0.45)",
            }}
          >
            <div style={{ width: 14, height: 14, borderRadius: 7, background: "#3DDC97", boxShadow: "0 0 12px #3DDC97" }} />
            <span style={{ fontSize: 40, fontWeight: 800, letterSpacing: "0.02em", color: C.white }}>{n.name}</span>
          </div>
        );
      })}

      <div style={{ position: "absolute", bottom: 64, width: "100%", display: "flex", justifyContent: "center" }}>
        <div style={{ position: "relative", display: "flex", gap: 12, padding: 10, borderRadius: 999, background: "rgba(255,255,255,0.05)", border: `1.5px solid ${C.line}`, opacity: interpolate(frame, [36, 46], [0, 1], clamp), translate: `0 ${interpolate(frame, [36, 50], [30, 0], { ...clamp, easing: EXPO_OUT })}px` }}>
          {LANGS.map((l, i) => {
            const on = Math.max(0, 1 - Math.abs(langPos - i));
            return (
              <div key={l} style={{ padding: "14px 34px", borderRadius: 999, fontSize: 36, fontWeight: 700, color: on > 0.5 ? "#0B0F2E" : C.mute, background: `rgba(255,178,56,${on})`, scale: `${1 + on * 0.04}` }}>
                {l}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
