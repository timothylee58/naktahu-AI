import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { BEAT, C, EXPO_OUT, Pill, Window, clamp, display, mono, pop, prog } from "./core";
import { Mark } from "../Promo/Mark";
import { TABLES, type Lang, tokens, useLang, useT } from "./i18n";

const UserBubble: React.FC<{ at?: number; size?: number }> = ({ at = 0, size = 34 }) => {
  const frame = useCurrentFrame();
  const t = useT();
  const p = pop(frame, at);
  return (
    <div style={{ display: "flex", justifyContent: "flex-end" }}>
      <div
        style={{
          ...p,
          transformOrigin: "100% 100%",
          maxWidth: 700,
          background: C.blue,
          color: "white",
          fontSize: size,
          fontWeight: 600,
          lineHeight: 1.3,
          padding: "22px 30px",
          borderRadius: "30px 30px 8px 30px",
          boxShadow: "0 18px 44px rgba(59,91,255,0.45)",
        }}
      >
        {t("chat.q")}
      </div>
    </div>
  );
};

const Avatar: React.FC<{ at: number }> = ({ at }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ width: 64, height: 64, flexShrink: 0 }}>
      <Mark frame={frame} size={64} bubbleAt={at} bloomAt={at + 3} id={`av${at}`} />
    </div>
  );
};

const Stamp: React.FC<{ n: number; label: string; at: number }> = ({ n, label, at }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ ...pop(frame, at), display: "inline-flex", alignItems: "center", gap: 12, padding: "12px 20px 12px 12px", borderRadius: 16, background: "rgba(59,91,255,0.14)", border: "1.5px solid rgba(123,145,255,0.5)" }}>
      <div style={{ width: 34, height: 34, borderRadius: 10, background: C.blue, color: "white", fontFamily: mono, fontSize: 20, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center" }}>{n}</div>
      <span style={{ fontSize: 26, fontWeight: 700 }}>{label}</span>
    </div>
  );
};

/** Bar 3 — the answer engine thinking. */
export const ChatMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const steps = [t("chat.step1"), t("chat.step2"), t("chat.step3")];
  return (
    <Window path="/chat">
      <div style={{ display: "flex", flexDirection: "column", gap: 34, height: "100%" }}>
        <div style={{ display: "flex", justifyContent: "center" }}>
          <Pill size={22} bg="rgba(61,220,151,0.12)" border="rgba(61,220,151,0.45)" color="#9CF0C8">
            <span style={{ width: 10, height: 10, borderRadius: 5, background: "#3DDC97", boxShadow: "0 0 10px #3DDC97" }} />
            {t("chat.verified")}
          </Pill>
        </div>
        <UserBubble at={0} />
        <div style={{ display: "flex", gap: 22 }}>
          <Avatar at={6} />
          <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingTop: 6 }}>
            {steps.map((s, i) => {
              const start = 12 + i * BEAT;
              const on = frame >= start;
              const done = frame >= start + BEAT;
              const p = prog(frame, start, 8);
              return (
                <div key={s} style={{ display: "flex", alignItems: "center", gap: 16, opacity: on ? 0.35 + 0.65 * p * (done ? 0.6 : 1) : 0, translate: `${(1 - p) * 30}px 0` }}>
                  <div style={{ width: 34, height: 34, borderRadius: 17, border: `2.5px solid ${done ? "#3DDC97" : C.blueHi}`, display: "flex", alignItems: "center", justifyContent: "center", background: done ? "rgba(61,220,151,0.15)" : "transparent" }}>
                    {done ? (
                      <svg width="18" height="18" viewBox="0 0 18 18"><path d="M3 9.5 L7.5 13.5 L15 5" stroke="#3DDC97" strokeWidth="2.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    ) : (
                      <div style={{ width: 12, height: 12, borderRadius: 6, background: C.blueHi, opacity: 0.5 + 0.5 * Math.sin(frame / 2) }} />
                    )}
                  </div>
                  <span style={{ fontFamily: mono, fontSize: 30, color: done ? C.mute : C.white }}>{s}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div style={{ marginTop: "auto", height: 92, borderRadius: 24, background: "rgba(255,255,255,0.05)", border: `1.5px solid ${C.line}`, display: "flex", alignItems: "center", padding: "0 28px", fontSize: 28, color: C.mute }}>
          {t("chat.queue")}
        </div>
      </div>
    </Window>
  );
};

/** Bar 4 — the answer streams in with numbered citation stamps. */
export const AnswerMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const words = tokens(t("ans.text"));
  const shown = interpolate(frame, [2, 30], [0, words.length], clamp);
  return (
    <Window path="/chat">
      <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
        <div style={{ opacity: 0.55, scale: "0.86", transformOrigin: "100% 0" }}>
          <UserBubble at={-20} size={30} />
        </div>
        <div style={{ display: "flex", gap: 22 }}>
          <Avatar at={-20} />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 26 }}>
            <div style={{ fontSize: 42, lineHeight: 1.38, fontWeight: 500, color: "#DCE1FF", letterSpacing: "-0.01em" }}>
              {words.map((w, i) => (
                <span key={i} style={{ opacity: Math.max(0, Math.min(1, shown - i)), fontWeight: w.startsWith("EzBiz") ? 800 : undefined, color: w.startsWith("EzBiz") ? "white" : undefined }}>
                  {w}
                </span>
              ))}
              <span style={{ display: "inline-block", width: 5, height: 44, background: C.blueHi, verticalAlign: "middle", opacity: frame < 30 && Math.floor(frame / 4) % 2 === 0 ? 1 : 0 }} />
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 14 }}>
              <Stamp n={1} label={t("ans.cite1")} at={BEAT * 2} />
              <Stamp n={2} label={t("ans.cite2")} at={BEAT * 2 + 5} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12, opacity: prog(frame, BEAT * 3, 8) }}>
              <div style={{ fontSize: 22, fontFamily: mono, letterSpacing: "0.12em", color: C.mute }}>{t("ans.followLabel")}</div>
              <div style={{ display: "flex", gap: 12 }}>
                <Pill size={24} bg="rgba(255,255,255,0.05)" border={C.line}>{t("ans.follow1")}</Pill>
                <Pill size={24} bg="rgba(255,255,255,0.05)" border={C.line}>{t("ans.follow2")}</Pill>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Window>
  );
};

/** Bar 5 — the citation popover and the DISAHKAN stamp. */
export const VerifiedMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const conf = interpolate(frame, [6, 30], [0, 0.94], { ...clamp, easing: EXPO_OUT });
  const stamp = prog(frame, BEAT * 2, 6);
  return (
    <Window path="/chat">
      <div style={{ position: "relative", height: "100%" }}>
        <Stamp n={1} label={t("ans.cite1")} at={-10} />
        <div
          style={{
            marginTop: 22,
            width: 720,
            borderRadius: 28,
            background: "rgba(14,19,52,0.98)",
            border: "1.5px solid rgba(140,160,255,0.35)",
            boxShadow: "0 30px 70px rgba(0,0,0,0.5)",
            padding: "34px 38px",
            display: "flex",
            flexDirection: "column",
            gap: 26,
            ...pop(frame, 2),
            transformOrigin: "0 0",
          }}
        >
          <div style={{ fontSize: 36, fontWeight: 800 }}>{t("ver.title")}</div>
          <div style={{ fontSize: 26, color: C.mute, marginTop: -14 }}>{t("ver.org")}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 28, fontWeight: 700 }}>
              <span>{t("ver.confidence")}</span>
              <span style={{ fontFamily: mono, color: "#3DDC97" }}>{Math.round(conf * 100)}%</span>
            </div>
            <div style={{ height: 14, borderRadius: 7, background: "rgba(255,255,255,0.08)" }}>
              <div style={{ width: `${conf * 100}%`, height: 14, borderRadius: 7, background: "linear-gradient(90deg,#1FB57A,#3DDC97)", boxShadow: "0 0 16px rgba(61,220,151,0.6)" }} />
            </div>
          </div>
          <div style={{ fontSize: 28, color: "#C9D0FF", opacity: prog(frame, 12, 8) }}>{t("ver.verified")}</div>
          <div style={{ opacity: prog(frame, 18, 8) }}>
            <Pill size={26} bg={C.blue} border={C.blue}>{t("ver.viewSource")}</Pill>
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            right: 10,
            bottom: 40,
            opacity: stamp,
            scale: `${2.2 - 1.2 * stamp}`,
            rotate: "-12deg",
            padding: "18px 38px",
            border: `8px solid ${C.blue}`,
            borderRadius: 18,
            color: C.blue,
            fontFamily: display,
            fontWeight: 800,
            fontSize: 76,
            letterSpacing: "0.08em",
            whiteSpace: "nowrap",
            background: "rgba(59,91,255,0.08)",
            boxShadow: `0 0 0 4px rgba(59,91,255,0.25) inset`,
            textShadow: "0 0 1px rgba(59,91,255,0.9)",
          }}
        >
          {t("ver.stamp")}
        </div>
      </div>
    </Window>
  );
};

const LANGS: { k: string; lang: Lang }[] = [
  { k: "BM", lang: "bm" },
  { k: "EN", lang: "en" },
  { k: "中文", lang: "zh" },
];

/** Bar 6 — the same answer in BM, English and Chinese, starting from the cut's own language. */
export const TranslateMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const lang = useLang();
  const order = [lang, ...LANGS.map((l) => l.lang).filter((l) => l !== lang)];
  const step = Math.min(2, Math.floor(frame / BEAT));
  const active = order[step];
  const local = frame - step * BEAT;
  const p = prog(local, 0, 7);
  return (
    <Window path="/chat">
      <div style={{ display: "flex", flexDirection: "column", gap: 40, height: "100%" }}>
        <div style={{ display: "flex", gap: 14, alignSelf: "center", padding: 10, borderRadius: 999, background: "rgba(255,255,255,0.05)", border: `1.5px solid ${C.line}` }}>
          {LANGS.map((l) => (
            <div key={l.k} style={{ padding: "14px 40px", borderRadius: 999, fontSize: 34, fontWeight: 800, background: l.lang === active ? C.amber : "transparent", color: l.lang === active ? "#1A1204" : C.mute, scale: l.lang === active ? `${1 + 0.06 * (1 - p)}` : "1" }}>
              {l.k}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 22 }}>
          <Avatar at={-20} />
          <div
            style={{
              flex: 1,
              fontSize: active === "zh" ? 48 : 46,
              lineHeight: 1.4,
              fontWeight: 600,
              color: "white",
              opacity: p,
              translate: `0 ${(1 - p) * 24}px`,
              filter: `blur(${(1 - p) * 8}px)`,
              minHeight: 260,
            }}
          >
            {TABLES[active]["ans.text"]}
          </div>
        </div>
        <div style={{ marginTop: "auto", fontSize: 24, color: C.mute, opacity: step > 0 ? 0.9 : 0 }}>
          {t("tr.notice")}
        </div>
      </div>
    </Window>
  );
};

/** Bar 7 — voice input with a beat-reactive waveform. */
export const VoiceMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const words = tokens(t("voice.text"));
  const shown = interpolate(frame, [8, 34], [0, words.length], clamp);
  const pulse = Math.exp(-(frame % BEAT) / 3.2);
  return (
    <Window path="/chat">
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 40, height: "100%", paddingTop: 20 }}>
        <div style={{ position: "relative", width: 200, height: 200, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {[0, 1].map((k) => (
            <div key={k} style={{ position: "absolute", inset: -30 - k * 34 - pulse * 18, borderRadius: 999, border: `3px solid rgba(255,90,95,${0.35 - k * 0.14})` }} />
          ))}
          <div style={{ width: 200, height: 200, borderRadius: 100, background: "radial-gradient(circle at 35% 30%, #FF7A7F, #E0283A)", boxShadow: `0 0 ${60 + pulse * 50}px rgba(255,70,80,0.6)`, display: "flex", alignItems: "center", justifyContent: "center", scale: `${1 + pulse * 0.05}` }}>
            <svg width="84" height="84" viewBox="0 0 24 24">
              <rect x="8.5" y="2.5" width="7" height="12" rx="3.5" fill="white" />
              <path d="M5 11 a7 7 0 0 0 14 0 M12 18 V21.5" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" />
            </svg>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 7, height: 110 }}>
          {Array.from({ length: 34 }).map((_, i) => {
            const h = 14 + Math.abs(Math.sin(i * 0.9 + frame * 0.45)) * 50 * (0.45 + pulse * 0.8) * (0.6 + 0.4 * Math.sin(i * 0.37));
            return <div key={i} style={{ width: 9, height: h, borderRadius: 5, background: i % 3 ? C.blueHi : "#FF7A7F", opacity: 0.9 }} />;
          })}
        </div>
        <div style={{ fontSize: 50, fontWeight: 800, letterSpacing: "-0.02em", textAlign: "center", minHeight: 70 }}>
          {words.map((w, i) => (
            <span key={i} style={{ opacity: Math.max(0, Math.min(1, shown - i)) }}>
              {w}
            </span>
          ))}
        </div>
        <div style={{ fontFamily: mono, fontSize: 24, letterSpacing: "0.16em", color: "#FF9A9E" }}>● {t("voice.label")}</div>
      </div>
    </Window>
  );
};

/** Bar 8 — share menu, then the public permalink page. */
export const ShareMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const page = frame >= BEAT * 2;
  const rows = [
    { t: t("share.copy"), c: C.mute },
    { t: t("share.wa"), c: "#25D366" },
    { t: t("share.tg"), c: "#2AABEE" },
    { t: t("share.fb"), c: "#1877F2" },
    { t: t("share.caption"), c: C.amber },
  ];
  const pageP = prog(frame, BEAT * 2, 9);
  return (
    <Window path={page ? "/a/Xq7Kp2" : "/chat"}>
      {!page ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14, width: 560, marginLeft: "auto", marginRight: "auto", marginTop: 20 }}>
          {rows.map((r, i) => {
            const hi = i === 1 && frame >= BEAT;
            return (
              <div
                key={r.t}
                style={{
                  ...pop(frame, i * 2),
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  padding: "22px 28px",
                  borderRadius: 20,
                  background: hi ? "rgba(37,211,102,0.16)" : "rgba(255,255,255,0.05)",
                  border: `1.5px solid ${hi ? "rgba(37,211,102,0.7)" : C.line}`,
                  fontSize: 32,
                  fontWeight: 700,
                }}
              >
                <div style={{ width: 22, height: 22, borderRadius: 11, background: r.c, boxShadow: `0 0 12px ${r.c}` }} />
                {r.t}
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 24, opacity: pageP, translate: `0 ${(1 - pageP) * 60}px` }}>
          <div style={{ fontSize: 24, fontFamily: mono, letterSpacing: "0.14em", color: C.amber }}>{t("share.header")}</div>
          <div style={{ fontSize: 40, fontWeight: 800, lineHeight: 1.2 }}>{t("chat.q")}</div>
          <div style={{ fontSize: 32, lineHeight: 1.4, color: "#CDD3FF" }}>{t("ans.text")}</div>
          <Stamp n={1} label={t("ans.cite1")} at={BEAT * 2 + 4} />
          <div style={{ display: "flex", alignItems: "center", gap: 20, marginTop: 6 }}>
            <Pill size={30} bg={C.blue} border={C.blue}>{t("share.cta")}</Pill>
          </div>
          <div style={{ fontSize: 22, color: C.mute }}>{t("share.disclaimer")}</div>
        </div>
      )}
    </Window>
  );
};
