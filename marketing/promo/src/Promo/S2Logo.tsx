import React from "react";
import { AbsoluteFill, Interactive, interpolate, random, useCurrentFrame } from "remotion";
import { C, EXPO_IN, EXPO_OUT, IN_OUT, clamp, display } from "./theme";
import { Mark } from "./Mark";

const WORD = "naktahu.my".split("");

export const S2Logo: React.FC = () => {
  const frame = useCurrentFrame();
  const lock = interpolate(frame, [50, 74], [0, 1], { ...clamp, easing: IN_OUT });
  const exit = interpolate(frame, [102, 116], [0, 1], { ...clamp, easing: EXPO_IN });
  const markSize = 380 - 150 * lock;

  return (
    <AbsoluteFill style={{ scale: `${interpolate(frame, [0, 98], [1, 1.04], clamp) + exit * 1.6}`, opacity: 1 - exit, filter: `blur(${exit * 22}px)` }}>
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        {[0, 5, 11].map((d, k) => {
          const p = interpolate(frame, [d, d + 26], [0, 1], { ...clamp, easing: EXPO_OUT });
          return (
            <div
              key={k}
              style={{
                position: "absolute",
                width: 1600 * p,
                height: 1600 * p,
                borderRadius: 9999,
                border: `${3 - k}px solid ${k === 1 ? C.amber : C.blueHi}`,
                opacity: (1 - p) * 0.8,
              }}
            />
          );
        })}
        <div
          style={{
            position: "absolute",
            width: 36,
            height: 36,
            borderRadius: 99,
            background: "white",
            scale: `${interpolate(frame, [0, 8], [1, 0], clamp)}`,
            boxShadow: "0 0 80px 30px rgba(123,145,255,0.9)",
          }}
        />
      </AbsoluteFill>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 44 * lock }}>
        <div style={{ display: "flex", alignItems: "center", gap: 44 * lock, translate: `0 ${-40 * lock}px` }}>
          <div style={{ position: "relative", width: markSize, height: markSize }}>
            <Mark frame={frame} size={markSize} bubbleAt={2} dotsFrom={8} bloomAt={28} id="s2" />
            {Array.from({ length: 18 }).map((_, i) => {
              const a = (i / 18) * Math.PI * 2 + random(`a${i}`) * 0.4;
              const p = interpolate(frame, [30, 60], [0, 1], { ...clamp, easing: EXPO_OUT });
              const dist = (90 + random(`d${i}`) * 170) * p;
              return (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: markSize * 0.81 + Math.cos(a) * dist,
                    top: markSize * 0.21 + Math.sin(a) * dist,
                    width: i % 3 === 0 ? 10 : 6,
                    height: i % 3 === 0 ? 10 : 6,
                    borderRadius: 9,
                    background: i % 2 ? C.amber : "#FF5A5F",
                    opacity: interpolate(frame, [30, 34, 56, 66], [0, 1, 0.8, 0], clamp),
                    boxShadow: `0 0 12px ${i % 2 ? C.amber : "#FF5A5F"}`,
                  }}
                />
              );
            })}
          </div>
          <div style={{ maxWidth: 1100 * lock, overflow: "hidden", display: "flex", whiteSpace: "nowrap", paddingBottom: 20, marginBottom: -20 }}>
            {WORD.map((ch, i) => {
              const p = interpolate(frame, [56 + i * 2, 56 + i * 2 + 18], [0, 1], { ...clamp, easing: EXPO_OUT });
              const isDomain = i >= 7;
              return (
                <span
                  key={i}
                  style={{
                    display: "inline-block",
                    fontFamily: display,
                    fontWeight: 800,
                    fontSize: 170,
                    letterSpacing: "-0.045em",
                    lineHeight: 1.05,
                    color: isDomain ? C.blue : C.white,
                    translate: `0 ${(1 - p) * 110}%`,
                    opacity: p,
                    filter: `blur(${(1 - p) * 6}px)`,
                    
                  }}
                >
                  {ch}
                </span>
              );
            })}
          </div>
        </div>
        <Interactive.Div
          name="Tagline"
          style={{
            fontFamily: display,
            fontSize: 62,
            fontWeight: 500,
            letterSpacing: "-0.015em",
            color: "rgba(244,246,255,0.88)",
            opacity: interpolate(frame, [72, 88], [0, 1], { ...clamp, easing: EXPO_OUT }),
            translate: interpolate(frame, [72, 88], ["0px 30px", "0px -40px"], { ...clamp, easing: EXPO_OUT }),
            filter: `blur(${interpolate(frame, [72, 88], [8, 0], clamp)}px)`,
          }}
        >
          Ilmu tempatan, jawapan seketika.
        </Interactive.Div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
