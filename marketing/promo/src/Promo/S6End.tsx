import React from "react";
import { AbsoluteFill, Interactive, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EXPO_OUT, clamp, display } from "./theme";
import { Mark } from "./Mark";

const WORD = "naktahu.my".split("");

export const S6End: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cta = spring({ frame: frame - 26, fps, config: { damping: 12 } });
  const shine = interpolate(frame, [44, 64], [-0.3, 1.3], clamp);

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", fontFamily: display, scale: `${interpolate(frame, [0, 84], [1.03, 1], clamp)}` }}>
      <div style={{ width: 250, height: 250, marginBottom: 26 }}>
        <Mark frame={frame} size={250} bubbleAt={0} bloomAt={6} id="s6" />
      </div>
      <div style={{ display: "flex", overflow: "hidden", paddingBottom: 14 }}>
        {WORD.map((ch, i) => {
          const p = interpolate(frame, [6 + i * 1.5, 22 + i * 1.5], [0, 1], { ...clamp, easing: EXPO_OUT });
          return (
            <span key={i} style={{ display: "inline-block", fontSize: 150, fontWeight: 800, letterSpacing: "-0.045em", lineHeight: 1.05, color: i >= 7 ? C.blue : C.white, translate: `0 ${(1 - p) * 110}%`, opacity: p }}>
              {ch}
            </span>
          );
        })}
      </div>
      <Interactive.Div
        name="End tagline"
        style={{
          fontSize: 52,
          fontWeight: 500,
          color: "rgba(244,246,255,0.85)",
          marginTop: 4,
          opacity: interpolate(frame, [16, 30], [0, 1], clamp),
          translate: interpolate(frame, [16, 30], ["0px 20px", "0px 0px"], { ...clamp, easing: EXPO_OUT }),
        }}
      >
        Ilmu tempatan, jawapan seketika.
      </Interactive.Div>
      <div
        style={{
          position: "relative",
          overflow: "hidden",
          marginTop: 52,
          padding: "26px 56px",
          borderRadius: 999,
          background: `linear-gradient(135deg, #5872FF, ${C.blueDeep})`,
          boxShadow: "0 20px 60px rgba(59,91,255,0.55), inset 0 1.5px 0 rgba(255,255,255,0.3)",
          fontSize: 44,
          fontWeight: 800,
          color: "white",
          letterSpacing: "-0.01em",
          scale: `${Math.max(0, cta)}`,
          opacity: Math.min(1, cta * 2),
        }}
      >
        Tanya sekarang — percuma →
        <div style={{ position: "absolute", top: 0, bottom: 0, left: `${shine * 100}%`, width: 140, translate: "-50% 0", background: "linear-gradient(100deg, transparent, rgba(255,255,255,0.45), transparent)", rotate: "12deg" }} />
      </div>
      <div style={{ position: "absolute", bottom: 60, fontSize: 26, color: C.mute, opacity: interpolate(frame, [34, 48], [0, 0.9], clamp) }}>
        Bukan nasihat rasmi kerajaan · naktahu.my
      </div>
    </AbsoluteFill>
  );
};
