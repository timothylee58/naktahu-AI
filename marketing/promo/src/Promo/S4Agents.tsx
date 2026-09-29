import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EXPO_OUT, clamp, display } from "./theme";
import { Stagger } from "./Shared";

const S = { stroke: "white", strokeWidth: 3.2, fill: "none", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

const AGENTS: { name: string; desc: string; from: string; to: string; icon: React.ReactNode }[] = [
  {
    name: "Compliance Drafter",
    desc: "Draf dokumen pematuhan",
    from: "#5872FF",
    to: "#2540C9",
    icon: (
      <g {...S}>
        <path d="M16 8 H34 L42 16 V44 H16 Z" />
        <path d="M34 8 V16 H42" />
        <path d="M22 25 H36 M22 31 H36 M22 37 H30" />
      </g>
    ),
  },
  {
    name: "Grant Finder",
    desc: "Padanan geran kerajaan",
    from: "#FFC25C",
    to: "#E08A00",
    icon: (
      <g {...S}>
        <circle cx="26" cy="28" r="15" />
        <circle cx="26" cy="28" r="8" />
        <circle cx="26" cy="28" r="1.5" fill="white" />
        <path d="M31 23 L42 12 M36 12 H42 V18" />
      </g>
    ),
  },
  {
    name: "Study Agent",
    desc: "Biasiswa & laluan pengajian",
    from: "#9B7BFF",
    to: "#5B3BDB",
    icon: (
      <g {...S}>
        <path d="M8 20 L26 11 L44 20 L26 29 Z" />
        <path d="M15 24 V34 C15 38 37 38 37 34 V24" />
        <path d="M44 20 V32" />
      </g>
    ),
  },
  {
    name: "Health Triage",
    desc: "Panduan awal kesihatan",
    from: "#FF6B7A",
    to: "#D12A45",
    icon: (
      <g {...S}>
        <path d="M26 42 C10 32 8 22 12 16 C16 10 24 11 26 17 C28 11 36 10 40 16 C44 22 42 32 26 42 Z" />
        <path d="M13 27 H20 L23 22 L28 32 L31 27 H39" />
      </g>
    ),
  },
  {
    name: "Immigration Navigator",
    desc: "Visa & permit, dipermudah",
    from: "#2FD3B5",
    to: "#119C84",
    icon: (
      <g {...S}>
        <circle cx="26" cy="26" r="16" />
        <path d="M10 26 H42 M26 10 C19 18 19 34 26 42 M26 10 C33 18 33 34 26 42" />
      </g>
    ),
  },
];

export const S4Agents: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const click = spring({ frame: frame - 76, fps, config: { damping: 12 } });
  const cur = spring({ frame: frame - 50, fps, config: { damping: 18, mass: 1.1 } });
  const cx = interpolate(cur, [0, 1], [1560, 652]);
  const cy = interpolate(cur, [0, 1], [1060, 612]);
  const ripple = interpolate(frame, [76, 98], [0, 1], { ...clamp, easing: EXPO_OUT });

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", top: 110, width: "100%" }}>
        <Stagger text="Lima ejen pakar. Satu tempat." frame={frame} start={2} accent={{ "Satu": C.blueHi, "tempat.": C.blueHi }} style={{ fontSize: 96, fontWeight: 800, letterSpacing: "-0.04em", color: C.white }} />
      </div>

      <div style={{ position: "absolute", inset: 0, perspective: 1800 }}>
        {AGENTS.map((a, i) => {
          const s = spring({ frame: frame - 10 - i * 3, fps, config: { damping: 14, mass: 0.9 } });
          const x = interpolate(s, [0, 1], [960, 300 + i * 330]);
          const picked = i === 1;
          const lift = picked ? click : 0;
          const dim = picked ? 0 : click;
          return (
            <div
              key={a.name}
              style={{
                position: "absolute",
                left: x - 150,
                top: 400 - lift * 34,
                width: 300,
                height: 420,
                transform: `rotateZ(${(1 - s) * (i - 2) * 9}deg) rotateY(${(1 - s) * (i - 2) * -30}deg) scale(${(0.8 + 0.2 * s) * (1 + lift * 0.05)})`,
                opacity: Math.min(1, s * 1.6) * (1 - dim * 0.55),
                filter: `blur(${dim * 2.5}px)`,
                borderRadius: 30,
                background: "linear-gradient(170deg, rgba(26,34,84,0.95), rgba(12,16,44,0.96))",
                border: `1.5px solid ${picked && lift > 0.1 ? `rgba(255,178,56,${0.4 + lift * 0.5})` : "rgba(140,160,255,0.2)"}`,
                boxShadow: picked ? `0 ${30 + lift * 40}px ${70 + lift * 50}px rgba(0,0,0,0.55), 0 0 ${lift * 80}px rgba(255,178,56,0.35)` : "0 30px 70px rgba(0,0,0,0.5)",
                padding: 30,
                display: "flex",
                flexDirection: "column",
                gap: 22,
                fontFamily: display,
                overflow: "hidden",
              }}
            >
              <div style={{ width: 104, height: 104, borderRadius: 28, background: `linear-gradient(145deg, ${a.from}, ${a.to})`, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 14px 34px ${a.to}88` }}>
                <svg width="60" height="60" viewBox="0 0 52 52">{a.icon}</svg>
              </div>
              <div style={{ fontSize: 38, fontWeight: 800, lineHeight: 1.08, letterSpacing: "-0.025em", color: C.white }}>{a.name}</div>
              <div style={{ fontSize: 27, lineHeight: 1.35, color: C.mute }}>{a.desc}</div>
              {picked && (
                <div
                  style={{
                    position: "absolute",
                    left: 30,
                    right: 30,
                    bottom: 28,
                    opacity: interpolate(frame, [82, 92], [0, 1], clamp),
                    translate: `0 ${interpolate(frame, [82, 94], [30, 0], { ...clamp, easing: EXPO_OUT })}px`,
                    padding: "14px 0",
                    borderRadius: 16,
                    background: C.amber,
                    color: "#1A1204",
                    fontSize: 24,
                    fontWeight: 800,
                    textAlign: "center",
                  }}
                >
                  Semak kelayakan →
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ position: "absolute", left: cx, top: cy, width: 0, height: 0 }}>
        <div
          style={{
            position: "absolute",
            left: -60 * ripple,
            top: -60 * ripple,
            width: 120 * ripple,
            height: 120 * ripple,
            borderRadius: 999,
            border: `3px solid ${C.amber}`,
            opacity: (1 - ripple) * (frame >= 76 ? 1 : 0),
          }}
        />
        <svg
          width="46"
          height="54"
          viewBox="0 0 46 54"
          style={{
            position: "absolute",
            left: -4,
            top: -2,
            opacity: interpolate(frame, [50, 56], [0, 1], clamp),
            scale: `${frame >= 74 && frame < 80 ? 0.85 : 1}`,
            filter: "drop-shadow(0 8px 14px rgba(0,0,0,0.5))",
          }}
        >
          <path d="M4 3 L4 42 L14 32 L21 49 L28 46 L21 30 L35 30 Z" fill="white" stroke="#0B0F2E" strokeWidth="3" strokeLinejoin="round" />
        </svg>
      </div>
    </AbsoluteFill>
  );
};
