import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, EXPO_OUT, IN_OUT, clamp, display, mono } from "./theme";
import { Eyebrow, Stagger } from "./Shared";
import { Mark } from "./Mark";

const QUERY = "Berapa kadar caruman KWSP majikan?";
const ANSWER = "Majikan mencarum 13% bagi pekerja bergaji RM5,000 ke bawah, dan 12% bagi gaji melebihi RM5,000.".split(" ");
const PIPE = ["Router", "Guard", "RAG", "Analyst", "Synthesiser"];

export const S3Demo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = interpolate(frame, [0, 34], [0, 1], { ...clamp, easing: EXPO_OUT });
  const settle = interpolate(frame, [0, 170], [0, 1], { ...clamp, easing: IN_OUT });
  const typed = Math.floor(interpolate(frame, [10, 42], [0, QUERY.length], clamp));
  const sent = frame >= 46;
  const press = spring({ frame: frame - 44, fps, config: { damping: 8, mass: 0.4 } });
  const userIn = spring({ frame: frame - 47, fps, config: { damping: 14 } });
  const words = interpolate(frame, [86, 118], [0, ANSWER.length], clamp);
  const hl = interpolate(frame, [120, 130], [0, 1], { ...clamp, easing: EXPO_OUT });
  const conf = interpolate(frame, [122, 144], [0, 0.92], { ...clamp, easing: EXPO_OUT });
  const answerIn = spring({ frame: frame - 84, fps, config: { damping: 15 } });

  return (
    <AbsoluteFill style={{ scale: `${1 + settle * 0.035}` }}>
      <div style={{ position: "absolute", left: 120, top: 250, width: 640, display: "flex", flexDirection: "column", gap: 34 }}>
        <Eyebrow frame={frame} start={2}>ENJIN JAWAPAN</Eyebrow>
        <div>
          <Stagger text="Tanya dalam BM" frame={frame} start={4} style={{ justifyContent: "flex-start", flexWrap: "nowrap", fontSize: 84, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1.04, color: C.white }} />
          <Stagger text="atau English." frame={frame} start={11} accent={{ "English.": C.blueHi }} style={{ justifyContent: "flex-start", flexWrap: "nowrap", fontSize: 84, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1.04, color: C.white }} />
        </div>
        <div
          style={{
            fontFamily: display,
            fontSize: 38,
            lineHeight: 1.35,
            color: C.mute,
            opacity: interpolate(frame, [22, 38], [0, 1], clamp),
            translate: `0 ${interpolate(frame, [22, 38], [24, 0], { ...clamp, easing: EXPO_OUT })}px`,
          }}
        >
          Jawapan bersumber rasmi, lengkap dengan sitasi — dalam saat.
        </div>
      </div>

      <div style={{ position: "absolute", left: 800, top: 130, width: 1020, height: 820, perspective: 2200 }}>
        <div
          style={{
            width: "100%",
            height: "100%",
            transform: `translateX(${(1 - enter) * 260}px) rotateY(${-24 + enter * 8 + settle * 9}deg) rotateX(${9 - settle * 5}deg)`,
            transformOrigin: "30% 50%",
            opacity: enter,
            borderRadius: 34,
            background: "linear-gradient(160deg, rgba(22,29,74,0.96), rgba(10,14,40,0.97))",
            border: "1.5px solid rgba(140,160,255,0.25)",
            boxShadow: "0 60px 140px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.03) inset, 0 0 120px rgba(59,91,255,0.18)",
            overflow: "hidden",
            fontFamily: display,
          }}
        >
          {/* chrome */}
          <div style={{ height: 70, display: "flex", alignItems: "center", gap: 12, padding: "0 28px", borderBottom: `1px solid ${C.line}` }}>
            {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
              <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c, opacity: 0.85 }} />
            ))}
            <div style={{ marginLeft: 24, flex: 1, height: 40, borderRadius: 12, background: "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", padding: "0 18px", gap: 10 }}>
              <svg width="16" height="18" viewBox="0 0 16 18"><rect x="1" y="8" width="14" height="10" rx="2" fill={C.mute} /><path d="M4 8 V5 a4 4 0 0 1 8 0 V8" stroke={C.mute} strokeWidth="2" fill="none" /></svg>
              <span style={{ fontFamily: mono, fontSize: 22, color: C.mute }}>naktahu.my/chat</span>
            </div>
          </div>

          {/* user message */}
          <div style={{ position: "absolute", right: 40, top: 110, opacity: sent ? userIn : 0, translate: `0 ${(1 - userIn) * 60}px`, scale: `${0.9 + 0.1 * userIn}`, transformOrigin: "100% 100%" }}>
            <div style={{ background: C.blue, color: "white", fontSize: 32, fontWeight: 600, padding: "20px 30px", borderRadius: "28px 28px 8px 28px", boxShadow: "0 16px 40px rgba(59,91,255,0.45)" }}>
              {QUERY}
            </div>
          </div>

          {/* pipeline */}
          <div style={{ position: "absolute", left: 40, top: 222, display: "flex", alignItems: "center", gap: 0 }}>
            {PIPE.map((p, i) => {
              const s = 56 + i * 6;
              const on = interpolate(frame, [s, s + 5], [0, 1], clamp);
              const vis = interpolate(frame, [52, 58], [0, 1], clamp);
              return (
                <React.Fragment key={p}>
                  {i > 0 && (
                    <div style={{ width: 34, height: 2, background: "rgba(140,160,255,0.2)", opacity: vis }}>
                      <div style={{ width: `${on * 100}%`, height: 2, background: C.blueHi }} />
                    </div>
                  )}
                  <div
                    style={{
                      opacity: vis,
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "9px 16px",
                      borderRadius: 999,
                      border: `1.5px solid ${on > 0.5 ? "rgba(123,145,255,0.7)" : "rgba(140,160,255,0.2)"}`,
                      background: on > 0.5 ? "rgba(59,91,255,0.18)" : "transparent",
                      scale: `${1 + Math.sin(on * Math.PI) * 0.12}`,
                    }}
                  >
                    <div style={{ width: 11, height: 11, borderRadius: 6, background: on > 0.5 ? C.blueHi : "rgba(140,160,255,0.3)", boxShadow: on > 0.5 ? `0 0 12px ${C.blueHi}` : "none" }} />
                    <span style={{ fontFamily: mono, fontSize: 20, color: on > 0.5 ? C.white : C.mute }}>{p}</span>
                  </div>
                </React.Fragment>
              );
            })}
          </div>

          {/* answer */}
          <div
            style={{
              position: "absolute",
              left: 40,
              right: 40,
              top: 300,
              opacity: answerIn,
              translate: `0 ${(1 - answerIn) * 40}px`,
              display: "flex",
              gap: 24,
            }}
          >
            <div style={{ flexShrink: 0, width: 64, height: 64 }}>
              <Mark frame={frame} size={64} bubbleAt={80} bloomAt={84} id="s3" />
            </div>
            <div style={{ flex: 1, background: "rgba(255,255,255,0.035)", border: `1px solid ${C.line}`, borderRadius: "8px 28px 28px 28px", padding: "28px 32px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
                <span style={{ fontFamily: mono, fontSize: 20, letterSpacing: "0.14em", color: C.amber }}>JAWAPAN · EPF</span>
                <div style={{ display: "flex", alignItems: "center", gap: 14, opacity: interpolate(frame, [120, 128], [0, 1], clamp) }}>
                  <svg width="58" height="58" viewBox="0 0 58 58">
                    <circle cx="29" cy="29" r="24" stroke="rgba(140,160,255,0.2)" strokeWidth="6" fill="none" />
                    <circle cx="29" cy="29" r="24" stroke="#3DDC97" strokeWidth="6" fill="none" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - conf} transform="rotate(-90 29 29)" />
                  </svg>
                  <div>
                    <div style={{ fontFamily: mono, fontSize: 15, letterSpacing: "0.16em", color: C.mute }}>KEYAKINAN</div>
                    <div style={{ fontFamily: mono, fontSize: 28, fontWeight: 500, color: "#3DDC97" }}>{conf.toFixed(2)}</div>
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 38, lineHeight: 1.45, color: "#D5DAFF", letterSpacing: "-0.01em" }}>
                {ANSWER.map((w, i) => {
                  const o = Math.max(0, Math.min(1, words - i));
                  const strong = w.includes("%");
                  return (
                    <span key={i} style={{ position: "relative", opacity: o, fontWeight: strong ? 800 : 400, color: strong ? "white" : undefined }}>
                      {i === 2 && (
                        <span style={{ position: "absolute", left: -6, right: -6, top: "12%", bottom: "8%", background: "rgba(255,178,56,0.42)", borderRadius: 6, scale: `${hl} 1`, transformOrigin: "0 50%" }} />
                      )}
                      <span style={{ position: "relative" }}>{w}</span>{" "}
                    </span>
                  );
                })}
                <span style={{ display: "inline-block", width: 4, height: 38, background: C.blueHi, verticalAlign: "middle", opacity: frame > 84 && frame < 120 && Math.floor(frame / 4) % 2 === 0 ? 1 : 0 }} />
              </div>
              <div style={{ display: "flex", gap: 14, marginTop: 26 }}>
                {[
                  { t: "KWSP · kwsp.gov.my", at: 118 },
                  { t: "Akta KWSP 1991", at: 124 },
                ].map((c) => {
                  const s = spring({ frame: frame - c.at, fps, config: { damping: 10, mass: 0.5 } });
                  return (
                    <div
                      key={c.t}
                      style={{
                        scale: `${Math.max(0, s)}`,
                        opacity: Math.min(1, s * 2),
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        padding: "10px 18px",
                        borderRadius: 999,
                        background: "rgba(59,91,255,0.16)",
                        border: "1.5px solid rgba(123,145,255,0.45)",
                        fontSize: 22,
                        fontWeight: 600,
                        color: C.white,
                      }}
                    >
                      <svg width="18" height="18" viewBox="0 0 18 18"><circle cx="9" cy="9" r="8" stroke={C.blueHi} strokeWidth="1.8" fill="none" /><path d="M5 9.5 L8 12 L13 6" stroke={C.blueHi} strokeWidth="2" fill="none" strokeLinecap="round" /></svg>
                      {c.t}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* input */}
          <div style={{ position: "absolute", left: 28, right: 28, bottom: 28, height: 92, borderRadius: 24, background: "rgba(255,255,255,0.05)", border: `1.5px solid ${frame < 46 ? "rgba(123,145,255,0.5)" : C.line}`, display: "flex", alignItems: "center", padding: "0 16px 0 30px" }}>
            <div style={{ flex: 1, fontSize: 32, color: sent ? C.mute : C.white, opacity: sent ? 0.55 : 1 }}>
              {sent ? "Tanya apa sahaja…" : QUERY.slice(0, typed)}
              {!sent && <span style={{ display: "inline-block", width: 3, height: 34, marginLeft: 3, background: C.blueHi, verticalAlign: "middle", opacity: Math.floor(frame / 5) % 2 === 0 || frame < 42 ? 1 : 0 }} />}
            </div>
            <div style={{ width: 62, height: 62, borderRadius: 18, background: C.blue, display: "flex", alignItems: "center", justifyContent: "center", scale: `${frame < 44 ? 1 : 0.86 + 0.14 * press}`, boxShadow: "0 10px 30px rgba(59,91,255,0.5)" }}>
              <svg width="28" height="28" viewBox="0 0 28 28"><path d="M14 22 V6 M7 13 L14 6 L21 13" stroke="white" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
