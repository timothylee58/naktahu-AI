import React from "react";
import { AbsoluteFill, Interactive, interpolate, random, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EXPO_IN, EXPO_OUT, clamp, mono } from "./theme";
import { Eyebrow, Stagger } from "./Shared";

type Kind = "site" | "pdf" | "err";
const TABS: { t: string; k: Kind }[] = [
  { t: "hasil.gov.my", k: "site" },
  { t: "Borang BE 2025.pdf", k: "pdf" },
  { t: "kwsp.gov.my", k: "site" },
  { t: "404 · Halaman tidak dijumpai", k: "err" },
  { t: "ssm.com.my", k: "site" },
  { t: "Garis Panduan (84 hlm).pdf", k: "pdf" },
  { t: "perkeso.gov.my", k: "site" },
  { t: "Sesi anda telah tamat", k: "err" },
  { t: "Soalan Lazim (FAQ)", k: "site" },
  { t: "jpn.gov.my", k: "site" },
  { t: "Pekeliling Bil. 3.pdf", k: "pdf" },
  { t: "Forum: “ada sesiapa tahu?”", k: "site" },
  { t: "imi.gov.my", k: "site" },
  { t: "Ralat 503", k: "err" },
  { t: "Jadual Caruman.pdf", k: "pdf" },
  { t: "moh.gov.my", k: "site" },
  { t: "Carian: “caruman majikan”", k: "site" },
  { t: "Log masuk semula", k: "err" },
  { t: "Akta 452.pdf", k: "pdf" },
  { t: "mida.gov.my", k: "site" },
  { t: "Hubungi kami", k: "site" },
  { t: "Muat turun gagal", k: "err" },
  { t: "Borang KWSP 6.pdf", k: "pdf" },
  { t: "portal myGOV", k: "site" },
];

const KIND = {
  site: { dot: C.blueHi, bg: "rgba(24,32,78,0.82)", border: "rgba(123,145,255,0.28)", color: C.white },
  pdf: { dot: C.amber, bg: "rgba(48,36,20,0.82)", border: "rgba(255,178,56,0.3)", color: "#FFE3B0" },
  err: { dot: "#FF5A5F", bg: "rgba(60,16,24,0.85)", border: "rgba(255,90,95,0.38)", color: "#FFC9CB" },
};

const Tab: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const { fps } = useVideoConfig();
  const tab = TABS[i];
  const k = KIND[tab.k];
  const a = i * 2.39996;
  const r = 340 + random(`r${i}`) * 400;
  const z = 0.62 + random(`z${i}`) * 0.62;
  const x0 = 960 + Math.cos(a) * r * 1.5;
  const y0 = 540 + Math.sin(a) * r * 0.78;
  const appear = 3 + i * 2.3;
  const pop = spring({ frame: frame - appear, fps, config: { damping: 11, mass: 0.6 } });
  const vx = (random(`vx${i}`) - 0.5) * 1.6 * z;
  const vy = (random(`vy${i}`) - 0.5) * 1.0 * z;
  const c = interpolate(frame, [60 + (i % 6), 82], [0, 1], { ...clamp, easing: EXPO_IN });
  const x = x0 + vx * frame;
  const y = y0 + vy * frame;
  const px = x + (960 - x) * c;
  const py = y + (540 - y) * c;
  const tilt = (random(`t${i}`) - 0.5) * 10;

  return (
    <div
      style={{
        position: "absolute",
        left: px,
        top: py,
        translate: "-50% -50%",
        scale: `${z * (0.55 + 0.45 * pop) * (1 - c)}`,
        rotate: `${tilt * (1 - pop) + tilt * 0.3 + c * (random(`s${i}`) * 240 - 120)}deg`,
        opacity: Math.min(1, pop * 2) * (1 - c * c) * (0.4 + 0.6 * ((z - 0.62) / 0.62)),
        filter: `blur(${Math.max(0, (1.0 - z) * 5)}px)`,
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "16px 26px 16px 20px",
        borderRadius: 16,
        background: k.bg,
        border: `1.5px solid ${k.border}`,
        boxShadow: "0 18px 40px rgba(0,0,0,0.45)",
        whiteSpace: "nowrap",
      }}
    >
      {tab.k === "pdf" ? (
        <div style={{ fontFamily: mono, fontSize: 16, fontWeight: 500, color: C.bg, background: C.amber, borderRadius: 5, padding: "2px 6px" }}>PDF</div>
      ) : (
        <div style={{ width: 14, height: 14, borderRadius: 7, background: k.dot, boxShadow: `0 0 14px ${k.dot}` }} />
      )}
      <div style={{ fontFamily: mono, fontSize: 30, color: k.color }}>{tab.t}</div>
      <div style={{ fontFamily: mono, fontSize: 24, color: k.color, opacity: 0.4, marginLeft: 8 }}>×</div>
    </div>
  );
};

export const S1Chaos: React.FC = () => {
  const frame = useCurrentFrame();
  const opened = TABS.filter((_, i) => frame >= 3 + i * 2.3).length;
  const shake = interpolate(frame, [24, 58, 64], [0, 5, 0], clamp);
  const strike = interpolate(frame, [56, 63], [0, 1], { ...clamp, easing: EXPO_OUT });
  const core = interpolate(frame, [72, 88], [0, 1], { ...clamp, easing: EXPO_OUT });

  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ translate: `${Math.sin(frame * 1.9) * shake}px ${Math.cos(frame * 2.3) * shake}px` }}>
        {TABS.map((_, i) => (
          <Tab key={i} i={i} frame={frame} />
        ))}
      </AbsoluteFill>

      <AbsoluteFill style={{ background: "radial-gradient(ellipse 820px 300px at 50% 50%, rgba(6,9,24,0.92) 30%, transparent 100%)" }} />

      <div style={{ position: "absolute", left: 104, top: 84, padding: "14px 18px", borderRadius: 14, background: "rgba(6,9,24,0.78)", zIndex: 5, opacity: interpolate(frame, [64, 74], [1, 0], clamp) }}>
        <Eyebrow frame={frame} start={2}>
          SOALAN: CARUMAN KWSP MAJIKAN?
        </Eyebrow>
      </div>

      <Interactive.Div
        name="Tab counter"
        style={{
          position: "absolute",
          right: 120,
          top: 82,
          textAlign: "right",
          opacity: interpolate(frame, [4, 14, 64, 74], [0, 1, 1, 0], clamp),
        }}
      >
        <div style={{ fontFamily: mono, fontSize: 22, letterSpacing: "0.18em", color: C.mute }}>TAB DIBUKA</div>
        <div style={{ fontFamily: mono, fontSize: 72, fontWeight: 500, color: opened > 14 ? "#FF6B70" : C.white, lineHeight: 1 }}>
          {String(opened).padStart(2, "0")}
        </div>
      </Interactive.Div>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ position: "absolute" }}>
          <Stagger text="Satu soalan." frame={frame} start={4} end={25} style={{ fontSize: 150, fontWeight: 800, letterSpacing: "-0.04em", color: C.white }} />
        </div>
        <div style={{ position: "absolute" }}>
          <Stagger text="Berpuluh tab." frame={frame} start={28} end={47} style={{ fontSize: 150, fontWeight: 800, letterSpacing: "-0.04em", color: C.white }} />
        </div>
        <div
          style={{
            position: "absolute",
            scale: `${interpolate(frame, [64, 80], [1, 0], { ...clamp, easing: EXPO_IN })}`,
            filter: `blur(${interpolate(frame, [64, 80], [0, 10], clamp)}px)`,
          }}
        >
          <Stagger text="Tiada jawapan." frame={frame} start={50} style={{ fontSize: 150, fontWeight: 800, letterSpacing: "-0.04em", color: C.white }} />
          <div
            style={{
              position: "absolute",
              left: -20,
              top: "54%",
              height: 12,
              width: `calc(${strike * 100}% + 40px)`,
              background: "#FF4D55",
              borderRadius: 6,
              rotate: "-2deg",
              opacity: strike > 0 ? 1 : 0,
              boxShadow: "0 0 30px rgba(255,77,85,0.7)",
            }}
          />
        </div>
      </AbsoluteFill>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            width: 44 * core,
            height: 44 * core,
            borderRadius: 999,
            background: "white",
            boxShadow: `0 0 ${90 * core}px ${36 * core}px rgba(123,145,255,0.95), 0 0 ${320 * core}px ${120 * core}px rgba(59,91,255,0.55)`,
          }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
