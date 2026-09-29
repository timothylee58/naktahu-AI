import React from "react";
import { useCurrentFrame } from "remotion";
import { Mark } from "../Promo/Mark";
import { C, EXPO_OUT, display, mono, prog, streamed, typed } from "./engine";
import { Abs, AppShell, Button, Card, Check, Chip, DemoFlag, Field, G, Rise, Spinner } from "./ui";
import type { Chapter, Script } from "./Walkthrough";

/**
 * Walkthrough 01 — Ask anything. One citizen, one question (the landing
 * page's own demo: child tax relief), followed from typing to sharing.
 * UI labels are the product's real EN strings (apps/web i18n).
 */

const Q = "How do I claim child tax relief?";
const ANSWER: Record<"en" | "bm" | "zh", string[]> = {
  en: [
    "Relief depends on your child's age and studies — up to RM8,000 a year per child in higher education, subject to current LHDN conditions.",
    "Claim it when you file your income tax return on MyTax (e-Filing), under the child relief section.",
    "Keep birth certificates and enrolment letters in case LHDN asks.",
  ],
  bm: [
    "Pelepasan bergantung pada umur dan pengajian anak — sehingga RM8,000 setahun bagi setiap anak di pengajian tinggi, tertakluk kepada syarat semasa LHDN.",
    "Tuntut semasa mengisi borang cukai pendapatan di MyTax (e-Filing), di bahagian pelepasan anak.",
    "Simpan sijil kelahiran dan surat pendaftaran sekiranya LHDN meminta.",
  ],
  zh: [
    "减免额视孩子的年龄与学业而定——每名就读高等教育的孩子每年最高可获RM8,000，须符合LHDN现行条件。",
    "在MyTax（e-Filing）申报所得税时，于子女减免一栏申请。",
    "请保存出生证明与入学信，以备LHDN查核。",
  ],
};
const SOURCES = [
  { n: 1, title: "2024 Tax Relief Schedule", agency: "LHDN", date: "1 Jan 2024" },
  { n: 2, title: "e-Filing (MyTax) guide", agency: "LHDN", date: "1 Mar 2026" },
];
const FOLLOWUPS = ["Which documents should I keep?", "When is the e-Filing deadline?", "Can I claim for a disabled child?"];
const HISTORY = [Q, "EPF withdrawal for a home", "Register a company with SSM"];

// ---------------------------------------------------------------- shared chat pieces
const InputBar: React.FC<{ value: string; focus?: boolean; placeholder?: string; rec?: number; press?: number; lang?: string }> = ({ value, focus, placeholder = "How do I register a company with SSM?", rec, press, lang = "EN" }) => {
  const frame = useCurrentFrame();
  const recording = rec !== undefined && frame >= rec;
  const lvl = (i: number) => 0.25 + 0.75 * Math.abs(Math.sin(frame / 3 + i * 1.7) * Math.sin(frame / 7 + i));
  return (
    <Abs x={360} y={900} w={1500} h={110}>
      <div style={{ position: "absolute", inset: 0, borderRadius: 28, background: "rgba(10,14,40,0.9)", border: `1.5px solid ${focus || recording ? C.blueHi : G.border}`, boxShadow: focus ? "0 0 0 5px rgba(123,145,255,0.16), 0 20px 60px rgba(0,0,0,0.4)" : "0 20px 60px rgba(0,0,0,0.4)", display: "flex", alignItems: "center", padding: "0 20px 0 32px", gap: 16 }}>
        <div style={{ flex: 1, fontSize: 28, color: value ? C.white : "rgba(139,147,196,0.75)", whiteSpace: "nowrap", overflow: "hidden" }}>
          {recording && !value ? (
            <div style={{ display: "flex", alignItems: "center", gap: 6, height: 50 }}>
              {Array.from({ length: 48 }, (_, i) => (
                <div key={i} style={{ width: 6, height: 50 * lvl(i), borderRadius: 3, background: C.blueHi, opacity: 0.85 }} />
              ))}
            </div>
          ) : (
            <>
              {value || placeholder}
              {focus && <span style={{ display: "inline-block", width: 3, height: 32, marginLeft: 3, background: C.blueHi, verticalAlign: "middle", opacity: Math.floor(frame / 8) % 2 ? 0 : 1 }} />}
            </>
          )}
        </div>
        <div style={{ padding: "8px 14px", borderRadius: 999, background: G.panel, border: `1px solid ${G.border}`, fontFamily: mono, fontSize: 18, color: C.mute }}>{lang}</div>
        {/* voice */}
        <div style={{ width: 70, height: 70, borderRadius: 35, display: "flex", alignItems: "center", justifyContent: "center", background: recording ? "rgba(230,30,37,0.85)" : G.panelHi, boxShadow: recording ? `0 0 0 ${8 + 6 * Math.sin(frame / 4)}px rgba(230,30,37,0.25)` : "none" }}>
          <svg width="30" height="30" viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="12" rx="3" fill="white" /><path d="M5 11 a7 7 0 0 0 14 0 M12 18 V21" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" /></svg>
        </div>
        {/* send */}
        <div style={{ width: 70, height: 70, borderRadius: 35, display: "flex", alignItems: "center", justifyContent: "center", background: value ? C.blue : G.panelHi, scale: press !== undefined && frame >= press - 2 && frame < press + 5 ? "0.9" : "1" }}>
          <svg width="30" height="30" viewBox="0 0 28 28"><path d="M14 22 V6 M7 13 L14 6 L21 13" stroke="white" strokeWidth="3.2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </div>
      </div>
      <div style={{ position: "absolute", left: 32, top: 120, fontSize: 17, color: "rgba(139,147,196,0.7)" }}>Enter to send · Ctrl+Enter · Esc to clear</div>
    </Abs>
  );
};

const Avatar: React.FC<{ at: number; x: number; y: number }> = ({ at, x, y }) => {
  const frame = useCurrentFrame();
  return (
    <Abs x={x} y={y} w={60} h={60}>
      <Mark frame={frame} size={60} bubbleAt={at} bloomAt={at + 3} id={`wa-${at}-${y}`} />
    </Abs>
  );
};

const UserBubble: React.FC<{ text: string; at: number; y: number }> = ({ text, at, y }) => {
  const frame = useCurrentFrame();
  const p = prog(frame, at, 12);
  return (
    <Abs x={960} y={y} w={900}>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <div style={{ opacity: p, scale: `${0.8 + 0.2 * p}`, transformOrigin: "100% 100%", background: C.blue, color: "white", fontSize: 30, fontWeight: 600, padding: "20px 30px", borderRadius: "28px 28px 8px 28px", boxShadow: "0 18px 44px rgba(59,91,255,0.4)" }}>{text}</div>
      </div>
    </Abs>
  );
};

const Thinking: React.FC<{ at: number; y: number; doneAt?: number }> = ({ at, y, doneAt = 1e9 }) => {
  const frame = useCurrentFrame();
  const steps = ["Searching knowledge base…", "Analysing information…", "Drafting response…"];
  if (frame >= doneAt) return null;
  return (
    <Abs x={460} y={y} w={800}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {steps.map((s, i) => {
          const st = at + i * 34;
          const on = frame >= st;
          const done = frame >= st + 34;
          const p = prog(frame, st, 10);
          return (
            <div key={s} style={{ display: "flex", alignItems: "center", gap: 16, opacity: on ? (done ? 0.55 : 1) * p : 0, fontSize: 27, color: C.white }}>
              <div style={{ width: 34, height: 34, borderRadius: 17, border: `2.5px solid ${done ? G.green : C.blueHi}`, display: "flex", alignItems: "center", justifyContent: "center", background: done ? G.greenSoft : "transparent" }}>
                {done ? <Check /> : <Spinner size={18} color={C.blueHi} />}
              </div>
              {s}
            </div>
          );
        })}
      </div>
    </Abs>
  );
};

/** The answer, streamed word by word from `at`, or instantly when `at` is in the past. `lang` swaps in a translation with a blur crossfade. */
const Answer: React.FC<{ at: number; y: number; langs?: { f: number; l: "en" | "bm" | "zh" }[]; sourcesAt?: number }> = ({ at, y, langs = [], sourcesAt }) => {
  const frame = useCurrentFrame();
  const cur = [...langs].reverse().find((k) => frame >= k.f);
  const lang = cur?.l ?? "en";
  const swap = cur ? prog(frame, cur.f, 14) : 1;
  const cjk = lang === "zh";
  let budget = Math.floor((frame - at) * 0.95);
  return (
    <>
      <Abs x={460} y={y} w={1300}>
        <div style={{ display: "flex", flexDirection: "column", gap: 18, fontSize: 30, lineHeight: 1.5, color: "rgba(244,246,255,0.95)", opacity: 0.3 + 0.7 * swap, filter: `blur(${(1 - swap) * 8}px)` }}>
          {ANSWER[lang].map((para, i) => {
            const units = cjk ? Array.from(para) : para.split(" ");
            const show = Math.max(0, Math.min(units.length, cur ? units.length : budget));
            budget -= units.length;
            if (show <= 0) return null;
            return (
              <div key={i}>
                {units.slice(0, show).join(cjk ? "" : " ")}
                {show === units.length && i < 2 && (
                  <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 30, height: 30, marginLeft: 8, borderRadius: 8, background: "rgba(59,91,255,0.3)", border: `1.5px solid ${C.blueHi}`, fontFamily: mono, fontSize: 17, verticalAlign: "middle" }}>{i + 1}</span>
                )}
              </div>
            );
          })}
        </div>
      </Abs>
      {sourcesAt !== undefined &&
        SOURCES.map((s, i) => {
          const p = prog(frame, sourcesAt + i * 5, 12);
          return (
            <Abs key={s.n} x={460 + i * 440} y={y + 340} w={420}>
              <div style={{ opacity: p, scale: `${0.8 + 0.2 * p}`, display: "flex", alignItems: "center", gap: 14, padding: "12px 18px 12px 12px", borderRadius: 16, background: "rgba(59,91,255,0.14)", border: "1.5px solid rgba(123,145,255,0.5)" }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: C.blue, fontFamily: mono, fontSize: 19, display: "flex", alignItems: "center", justifyContent: "center" }}>{s.n}</div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: 21, fontWeight: 700 }}>{s.title}</span>
                  <span style={{ fontFamily: mono, fontSize: 15, color: C.mute }}>{s.agency} · {s.date}</span>
                </div>
              </div>
            </Abs>
          );
        })}
    </>
  );
};

const ACTIONS = [
  { k: "Copy", x: 460, w: 110 },
  { k: "Share", x: 586, w: 120 },
  { k: "Translate answer", x: 722, w: 240 },
  { k: "Regenerate response", x: 978, w: 280 },
];
const ActionRow: React.FC<{ y: number; at: number; hot?: string }> = ({ y, at, hot }) => {
  const frame = useCurrentFrame();
  return (
    <>
      {ACTIONS.map((a, i) => (
        <Abs key={a.k} x={a.x} y={y} w={a.w} h={48}>
          <div style={{ opacity: prog(frame, at + i * 3, 10), height: 48, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 600, color: hot === a.k ? C.white : C.mute, background: hot === a.k ? "rgba(59,91,255,0.25)" : G.panel, border: `1.5px solid ${hot === a.k ? C.blueHi : G.border}` }}>{a.k}</div>
        </Abs>
      ))}
      <Abs x={1274} y={y} w={140} h={48}>
        <div style={{ opacity: prog(frame, at + 12, 10), display: "flex", gap: 10, height: 48, alignItems: "center", fontSize: 22, color: C.mute }}>👍 👎</div>
      </Abs>
    </>
  );
};
const actionCenter = (k: string, y: number) => {
  const a = ACTIONS.find((x) => x.k === k)!;
  return { x: a.x + a.w / 2, y: y + 24 };
};

const Menu: React.FC<{ x: number; y: number; w: number; items: string[]; at: number; to?: number; hot?: number }> = ({ x, y, w, items, at, to = 1e9, hot }) => {
  const frame = useCurrentFrame();
  const p = Math.min(prog(frame, at, 10), 1 - prog(frame, to, 6));
  if (p <= 0) return null;
  return (
    <Abs x={x} y={y} w={w}>
      <div style={{ opacity: p, scale: `${0.94 + 0.06 * p}`, transformOrigin: "20% 0%", background: "rgba(16,21,56,0.98)", border: `1.5px solid ${G.border}`, borderRadius: 18, padding: 8, boxShadow: "0 30px 70px rgba(0,0,0,0.55)" }}>
        {items.map((it, i) => (
          <div key={it} style={{ height: 52, display: "flex", alignItems: "center", padding: "0 18px", borderRadius: 12, fontSize: 22, fontWeight: 600, background: hot === i ? "rgba(59,91,255,0.3)" : "transparent" }}>{it}</div>
        ))}
      </div>
    </Abs>
  );
};
/** Centre of menu item `i` for a Menu at (x, y). */
const menuItem = (x: number, y: number, i: number) => ({ x: x + 150, y: y + 8 + i * 52 + 26 });

const Toast: React.FC<{ text: string; at: number; dur?: number }> = ({ text, at, dur = 60 }) => {
  const frame = useCurrentFrame();
  const p = Math.min(prog(frame, at, 10), 1 - prog(frame, at + dur, 8));
  if (p <= 0) return null;
  return (
    <Abs x={960} y={130} w={300}>
      <div style={{ opacity: p, translate: `0 ${(1 - p) * -20}px`, display: "flex", alignItems: "center", gap: 12, justifyContent: "center", padding: "14px 22px", borderRadius: 16, background: G.greenSoft, border: `1.5px solid ${G.green}`, fontSize: 22, fontWeight: 700 }}>
        <Check /> {text}
      </div>
    </Abs>
  );
};

// ---------------------------------------------------------------- chapter 1: ask
const C1 = { start: 120, chat: 132, focus: 172, type: 182, send: 262, think: 280 };
const LandingOrChat: React.FC = () => {
  const frame = useCurrentFrame();
  const landing = frame < C1.chat;
  const sent = frame >= C1.send;
  return (
    <AppShell active="Home">
      {landing ? (
        <>
          <Abs x={300} y={200} w={1620}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 26, textAlign: "center" }}>
              <Rise at={0}><Chip on size={20}>🇲🇾 Built for Malaysia</Chip></Rise>
              <Rise at={4}>
                <div style={{ fontSize: 78, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1.05, maxWidth: 1250 }}>
                  Ask anything about the <span style={{ color: C.blueHi }}>Malaysian government.</span>
                </div>
              </Rise>
              <Rise at={9}><div style={{ fontSize: 30, color: C.mute }}>Ask once. Know now.</div></Rise>
            </div>
          </Abs>
          <Abs x={820} y={580}><Rise at={12}><Button press={C1.start} size={24}>Start Asking</Button></Rise></Abs>
          <Abs x={1100} y={580}><Rise at={14}><Button kind="ghost" size={24}>Explore AI Agents</Button></Rise></Abs>
          <Abs x={830} y={700} w={540}><Rise at={16}><Field value="" placeholder="Your postcode (e.g. 50450)" /></Rise></Abs>
          <Abs x={300} y={880} w={1620}>
            <Rise at={18}>
              <div style={{ display: "flex", justifyContent: "center", gap: 16, fontFamily: mono, fontSize: 20, color: C.mute, letterSpacing: "0.1em" }}>
                {["LHDN", "KWSP", "SSM", "PERKESO", "KKM", "JPN"].map((a) => (
                  <span key={a} style={{ padding: "10px 18px", borderRadius: 12, border: `1px solid ${G.border}` }}>{a}</span>
                ))}
              </div>
            </Rise>
          </Abs>
        </>
      ) : (
        <>
          {!sent && (
            <Abs x={300} y={190} w={1620}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 26 }}>
                <Rise at={C1.chat}><div style={{ fontSize: 58, fontWeight: 800, letterSpacing: "-0.035em" }}>What do you need to know today?</div></Rise>
                <Rise at={C1.chat + 4}>
                  <div style={{ display: "flex", gap: 14 }}>
                    <Chip on tone="blue">● Bilingual engine active</Chip>
                    <Chip on tone="green">● gov.my sources verified</Chip>
                  </div>
                </Rise>
                <Rise at={C1.chat + 8}>
                  <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
                    {["Tax & EPF", "Business & Grants", "Immigration & Documents", "Civic & Education"].map((t, i) => (
                      <Chip key={t} on={i === 0} size={21}>{t}</Chip>
                    ))}
                  </div>
                </Rise>
                <Rise at={C1.chat + 12}>
                  <div style={{ display: "flex", gap: 12 }}>
                    {["How to pay taxes", "EPF withdrawal", "PTPTN education loan"].map((t) => (
                      <Chip key={t} size={21}>{t}</Chip>
                    ))}
                  </div>
                </Rise>
              </div>
            </Abs>
          )}
          {sent && (
            <>
              <UserBubble text={Q} at={C1.send + 2} y={150} />
              <Avatar at={C1.think} x={380} y={260} />
              <Thinking at={C1.think + 4} y={270} />
            </>
          )}
          <InputBar value={sent ? "" : typed(Q, frame, C1.type, 2.2)} focus={frame >= C1.focus && !sent} press={C1.send} />
        </>
      )}
    </AppShell>
  );
};

const ch1: Chapter = {
  name: "Ask",
  title: "Ask",
  line: "Plain words, straight to an answer.",
  Screen: LandingOrChat,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 960, y: 540, z: 1 },
    { f: 104, x: 1000, y: 560, z: 1.45 },
    { f: 132, x: 1080, y: 560, z: 1.05 },
    { f: 176, x: 1300, y: 900, z: 1.75 },
    { f: 262, x: 1300, y: 900, z: 1.75 },
    { f: 300, x: 1000, y: 330, z: 1.55 },
  ],
  cursor: [
    { f: 64, x: 1400, y: 800 },
    { f: C1.start, x: 950, y: 612, click: true },
    { f: C1.focus, x: 900, y: 955, click: true },
    { f: C1.send - 4, x: 1795, y: 955 },
    { f: C1.send, x: 1795, y: 955, click: true },
    { f: C1.send + 40, x: 1750, y: 760 },
  ],
  callouts: [{ f: 190, to: 262, x: 1690, y: 915, text: "Voice input", side: "top" }],
  captions: [
    { f: 64, to: 170, text: "Start on naktahu.my.", detail: "Ask right away — free, no credit card needed." },
    { f: 176, to: 300, text: "Type your question in plain words.", detail: "No keywords, no forms." },
    { f: 300, to: 470, text: "It searches before it speaks.", detail: "Knowledge base → analysis → drafting, live on screen." },
  ],
};

// ---------------------------------------------------------------- chapter 2: verify
const C2 = { stream: 40, sources: 190, hover: 250, pop: 262 };
const Grounded: React.FC = () => {
  const frame = useCurrentFrame();
  const popP = Math.min(prog(frame, C2.pop, 12), 1 - prog(frame, 440, 8));
  return (
    <AppShell active="Home">
      <UserBubble text={Q} at={-20} y={150} />
      <Avatar at={-20} x={380} y={260} />
      <Answer at={C2.stream} y={265} sourcesAt={C2.sources} />
      <ActionRow y={700} at={C2.sources + 10} />
      <InputBar value="" />
      <DemoFlag />
      {popP > 0 && (
        <Abs x={460} y={410} w={520}>
          <div style={{ opacity: popP, scale: `${0.9 + 0.1 * popP}`, transformOrigin: "20% 100%", padding: 26, borderRadius: 22, background: "rgba(16,21,56,0.98)", border: `1.5px solid ${C.blueHi}`, boxShadow: "0 30px 70px rgba(0,0,0,0.6)", display: "flex", flexDirection: "column", gap: 14, fontSize: 22 }}>
            <div style={{ fontSize: 24, fontWeight: 800 }}>2024 Tax Relief Schedule</div>
            <div style={{ color: C.mute }}>In effect from 1 Jan 2024</div>
            <div style={{ display: "flex", gap: 12 }}>
              <Chip on tone="green" size={18}>Confidence: 92%</Chip>
              <Chip size={18}>Verified 12 Sep 2026</Chip>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, color: C.blueHi, fontWeight: 700 }}>View official source ↗ <span style={{ fontFamily: mono, fontSize: 18, color: C.mute }}>hasil.gov.my</span></div>
          </div>
        </Abs>
      )}
    </AppShell>
  );
};

const ch2: Chapter = {
  name: "Verify",
  title: "Verify",
  line: "Every claim, linked to its official source.",
  Screen: Grounded,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 1060, y: 420, z: 1.4 },
    { f: 190, x: 1060, y: 470, z: 1.4 },
    { f: 240, x: 900, y: 560, z: 1.6 },
    { f: 280, x: 860, y: 520, z: 1.65 },
    { f: 440, x: 860, y: 520, z: 1.65 },
    { f: 470, x: 1000, y: 540, z: 1.2 },
  ],
  cursor: [
    { f: 200, x: 1300, y: 820 },
    { f: C2.hover, x: 620, y: 640, click: true },
    { f: 400, x: 600, y: 650 },
  ],
  callouts: [
    { f: 300, to: 440, x: 980, y: 480, text: "Real gov.my source — never invented", side: "right" },
  ],
  spots: [{ f: 280, to: 440, x: 460, y: 410, w: 520, h: 230 }],
  captions: [
    { f: 64, to: 190, text: "The answer streams in as it's written.", detail: "Grounded in Malaysian government sources, not the open web." },
    { f: 196, to: 300, text: "Every claim is numbered.", detail: "Each number is a source you can open." },
    { f: 300, to: 470, text: "Check it yourself.", detail: "When it took effect, how confident the match is, and the official page." },
  ],
};

// ---------------------------------------------------------------- chapter 3: your language
const T_BTN = actionCenter("Translate answer", 700);
const MENU = { x: 722, y: 756, w: 300 };
const C3 = { t1: 70, bm: 104, t2: 190, zh: 222, mic: 300, heard: 340 };
const VOICE_Q = "Macam mana nak keluarkan KWSP untuk beli rumah?";
const Language: React.FC = () => {
  const frame = useCurrentFrame();
  const menu1 = frame >= C3.t1 && frame < C3.bm + 6;
  const menu2 = frame >= C3.t2 && frame < C3.zh + 6;
  return (
    <AppShell active="Home" lang={frame >= C3.zh ? "中文" : frame >= C3.bm ? "BM" : "EN"}>
      <UserBubble text={Q} at={-20} y={150} />
      <Avatar at={-20} x={380} y={260} />
      <Answer at={-400} y={265} sourcesAt={-40} langs={[{ f: C3.bm, l: "bm" }, { f: C3.zh, l: "zh" }]} />
      <ActionRow y={700} at={-40} hot={menu1 || menu2 ? "Translate answer" : undefined} />
      <InputBar value={frame >= C3.heard ? typed(VOICE_Q, frame, C3.heard, 1.1) : ""} rec={frame >= C3.mic && frame < 430 ? C3.mic : undefined} focus={frame >= 430} lang={frame >= C3.mic ? "BM" : "EN"} />
      <DemoFlag />
      {menu1 && <Menu {...MENU} items={["Bahasa Malaysia", "中文", "English"]} at={C3.t1 + 2} hot={frame >= C3.bm - 8 ? 0 : undefined} />}
      {menu2 && <Menu {...MENU} items={["Bahasa Malaysia", "中文", "English"]} at={C3.t2 + 2} hot={frame >= C3.zh - 8 ? 1 : undefined} />}
    </AppShell>
  );
};

const ch3: Chapter = {
  name: "Your language",
  title: "Your language",
  line: "BM · English · 中文 — typed or spoken.",
  Screen: Language,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 64, x: 980, y: 560, z: 1.35 },
    { f: 280, x: 980, y: 560, z: 1.35 },
    { f: 320, x: 1350, y: 900, z: 1.7 },
    { f: 470, x: 1350, y: 900, z: 1.7 },
  ],
  cursor: [
    { f: 50, x: 1300, y: 600 },
    { f: C3.t1, ...T_BTN, click: true },
    { f: C3.bm, ...menuItem(MENU.x, MENU.y, 0), click: true },
    { f: C3.t2, ...T_BTN, click: true },
    { f: C3.zh, ...menuItem(MENU.x, MENU.y, 1), click: true },
    { f: C3.mic, x: 1690, y: 955, click: true },
    { f: 420, x: 1640, y: 1020 },
  ],
  callouts: [{ f: 320, to: 460, x: 1690, y: 915, text: "BM voice input · Pro", side: "top" }],
  captions: [
    { f: 64, to: 190, text: "Switch the answer to Bahasa Malaysia…", detail: "Same answer, same sources — just in your language." },
    { f: 196, to: 300, text: "…or 中文, in one click.", detail: "BM · English · 中文, all the way through." },
    { f: 306, to: 470, text: "Or just say it.", detail: "Speak in BM and your words become the question." },
  ],
};

// ---------------------------------------------------------------- chapter 4: share
const S_BTN = actionCenter("Share", 700);
const SMENU = { x: 586, y: 756, w: 380 };
const C4 = { share: 50, copy: 96, page: 170 };
const Share: React.FC = () => {
  const frame = useCurrentFrame();
  if (frame < C4.page) {
    return (
      <AppShell active="Home">
        <UserBubble text={Q} at={-20} y={150} />
        <Avatar at={-20} x={380} y={260} />
        <Answer at={-400} y={265} sourcesAt={-40} />
        <ActionRow y={700} at={-40} hot={frame >= C4.share && frame < C4.copy + 6 ? "Share" : undefined} />
        <InputBar value="" />
      <DemoFlag />
        {frame >= C4.share && frame < C4.copy + 6 && (
          <Menu {...SMENU} items={["Copy link", "Share to WhatsApp", "Share to Telegram", "Share to Facebook", "Draft a caption (AI)"]} at={C4.share + 2} hot={frame >= C4.copy - 8 ? 0 : undefined} />
        )}
        <Toast text="Link copied!" at={C4.copy + 4} />
      </AppShell>
    );
  }
  // the public share page: no sidebar, anyone with the link can read it
  const p = prog(frame, C4.page, 16);
  return (
    <div style={{ position: "absolute", inset: 0, borderRadius: 34, overflow: "hidden", background: "linear-gradient(160deg, #0E1438, #080C26)", border: `1.5px solid ${G.border}`, fontFamily: display, color: C.white, opacity: p }}>
      <div style={{ height: 80, display: "flex", alignItems: "center", gap: 14, padding: "0 32px", borderBottom: `1px solid ${G.border}`, background: "rgba(5,8,28,0.6)" }}>
        {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c, opacity: 0.85 }} />)}
        <div style={{ marginLeft: 20, flex: 1, maxWidth: 900, height: 46, borderRadius: 14, background: G.panel, display: "flex", alignItems: "center", padding: "0 20px", fontFamily: mono, fontSize: 21, color: C.mute }}>🔒 naktahu.my/a/k7Q2mX</div>
      </div>
      <div style={{ position: "absolute", top: 80, left: 0, right: 0, height: 100, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 240px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 48, height: 48 }}><Mark frame={200} size={48} bubbleAt={0} bloomAt={0} id="sharehdr" /></div>
          <span style={{ fontSize: 32, fontWeight: 800 }}>naktahu<span style={{ color: C.blue }}>.my</span></span>
          <span style={{ fontSize: 22, color: C.mute, marginLeft: 12 }}>Ask about government</span>
        </div>
        <Button size={22}>Ask NakTahu</Button>
      </div>
      <div style={{ position: "absolute", top: 210, left: 240, right: 240 }}>
        <Card style={{ padding: 44, display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 40, fontWeight: 800, letterSpacing: "-0.02em" }}>{Q}</div>
          {ANSWER.en.map((a) => <div key={a} style={{ fontSize: 27, lineHeight: 1.5, color: "rgba(244,246,255,0.9)" }}>{a}</div>)}
          <div style={{ display: "flex", gap: 16 }}>
            {SOURCES.map((s) => <Chip key={s.n} on size={19}>{s.n} · {s.title}</Chip>)}
          </div>
        </Card>
        <div style={{ marginTop: 26, fontSize: 21, color: C.mute, textAlign: "center" }}>Shared from NakTahu AI. Verify important information against official sources.</div>
      </div>
      <DemoFlag />
    </div>
  );
};

const ch4: Chapter = {
  name: "Share",
  title: "Share",
  line: "Send a verified answer in one tap.",
  Screen: Share,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 46, x: 820, y: 780, z: 1.6 },
    { f: 150, x: 820, y: 780, z: 1.6 },
    { f: 176, x: 960, y: 540, z: 1 },
    { f: 250, x: 960, y: 540, z: 1.05 },
    { f: 300, x: 960, y: 450, z: 1.3 },
    { f: 380, x: 960, y: 690, z: 1.55 },
    { f: 470, x: 960, y: 540, z: 1.1 },
  ],
  cursor: [
    { f: 30, x: 1100, y: 900 },
    { f: C4.share, ...S_BTN, click: true },
    { f: C4.copy, ...menuItem(SMENU.x, SMENU.y, 0), click: true },
    { f: 150, x: 900, y: 640, hide: true },
  ],
  callouts: [{ f: 110, to: 160, x: 960, y: 160, text: "Copied to clipboard", side: "bottom", color: "#3DDC97" }],
  captions: [
    { f: 50, to: 170, text: "Share it where people actually talk.", detail: "Copy link, WhatsApp, Telegram, Facebook — or draft a caption with AI." },
    { f: 176, to: 330, text: "They see the answer and its sources.", detail: "No account needed to read a shared answer." },
    { f: 330, to: 470, text: "And a gentle reminder to verify.", detail: "Shared answers always carry the official-source disclaimer." },
  ],
};

// ---------------------------------------------------------------- chapter 5: go deeper
const C5 = { follow: 64, scroll: 76, history: 220, type: 300, suggest: 348, open: 400 };
const FU_Y = 670;
const FU_X = [460, 890, 1320];
const Deeper: React.FC = () => {
  const frame = useCurrentFrame();
  const scroll = prog(frame, C5.scroll, 20) * 480;
  const suggestP = prog(frame, C5.suggest, 12);
  return (
    <AppShell active="Home" history={{ today: HISTORY, earlier: ["Lost MyKad", "Register to vote"], highlight: frame >= C5.history ? 0 : undefined }}>
      <div style={{ position: "absolute", inset: 0, translate: `0 ${-scroll}px` }}>
        <UserBubble text={Q} at={-20} y={150} />
        <Avatar at={-20} x={380} y={260} />
        <Answer at={-400} y={265} sourcesAt={-40} />
        <Abs x={460} y={FU_Y - 44} w={600}><div style={{ fontSize: 20, fontWeight: 700, color: C.mute }}>Suggested follow-ups</div></Abs>
        {FOLLOWUPS.map((t, i) => (
          <Abs key={t} x={FU_X[i]} y={FU_Y} w={410}>
            <div style={{ height: 56, borderRadius: 999, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, fontWeight: 600, background: i === 0 && frame >= C5.follow ? "rgba(59,91,255,0.3)" : G.panel, border: `1.5px solid ${i === 0 && frame >= C5.follow ? C.blueHi : G.border}` }}>{t}</div>
          </Abs>
        ))}
        <UserBubble text={FOLLOWUPS[0]} at={C5.scroll + 6} y={790} />
        <Avatar at={C5.scroll + 14} x={380} y={890} />
        <Abs x={460} y={900} w={1300}>
          <div style={{ fontSize: 30, lineHeight: 1.5, color: "rgba(244,246,255,0.95)" }}>
            {streamed("Keep your child's birth certificate, plus proof of enrolment for any child in higher education. LHDN can ask for them for up to 7 years.", frame, C5.scroll + 22, 0.8)}
          </div>
        </Abs>
      </div>
      <InputBar value={frame >= C5.type ? typed("Grants I qualify for", frame, C5.type, 2) : ""} focus={frame >= C5.type - 10} />
      <DemoFlag />
      {suggestP > 0 && (
        <Abs x={360} y={800} w={1500}>
          <div style={{ opacity: suggestP, translate: `0 ${(1 - suggestP) * 20}px`, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px 14px 26px", borderRadius: 20, background: "rgba(255,178,56,0.12)", border: "1.5px solid rgba(255,178,56,0.55)", fontSize: 23, fontWeight: 600 }}>
            <span>✦ This looks like a <b style={{ color: C.amber }}>Grant Finder</b> question</span>
            <Button size={20} press={C5.open}>Open →</Button>
          </div>
        </Abs>
      )}
    </AppShell>
  );
};

const ch5: Chapter = {
  name: "Go deeper",
  title: "Go deeper",
  line: "Follow-ups, history, and the right agent.",
  Screen: Deeper,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 56, x: 1100, y: 640, z: 1.35 },
    { f: 190, x: 1100, y: 520, z: 1.3 },
    { f: 226, x: 420, y: 520, z: 1.8 },
    { f: 290, x: 420, y: 520, z: 1.8 },
    { f: 326, x: 1250, y: 860, z: 1.55 },
    { f: 470, x: 1250, y: 860, z: 1.55 },
  ],
  cursor: [
    { f: 40, x: 1200, y: 560 },
    { f: C5.follow, x: 665, y: 698, click: true },
    { f: C5.history, x: 150, y: 612, click: true },
    { f: C5.type - 12, x: 900, y: 955, click: true },
    { f: C5.open, x: 1790, y: 832, click: true },
  ],
  callouts: [
    { f: 232, to: 300, x: 290, y: 612, text: "Query history · Pro", side: "right" },
    { f: 360, to: 460, x: 1100, y: 800, text: "Routes you to the right agent", side: "top" },
  ],
  captions: [
    { f: 56, to: 200, text: "Suggested follow-ups keep you moving.", detail: "One tap asks the next obvious question." },
    { f: 206, to: 310, text: "Everything you asked, saved.", detail: "Query history, grouped by day." },
    { f: 316, to: 470, text: "Bigger task? NakTahu spots it.", detail: "It suggests the specialised agent built for the job." },
  ],
};

export const ASK: Script = {
  id: "ask",
  series: "WALKTHROUGH 01 · ASK ANYTHING",
  number: "01",
  name: "Ask anything",
  tagline: "Ask once. Know now.",
  hook: {
    lines: ["Stop searching.", "Just ask."],
    accent: 1,
    chaos: ["hasil.gov.my — Tax relief", "forum: child relief 2024??", "e-Filing guide (PDF, 84 pages)", "blog: 10 reliefs you missed", "MyTax — login", "news: budget tax changes", "thread: is it RM2k or RM8k?", "KWSP — i-Akaun"],
  },
  chapters: [ch1, ch2, ch3, ch4, ch5],
  recap: { lines: ["Ask.", "Verify.", "Share."], plan: "FREE", planDetail: "25 questions a day — free, no credit card needed" },
  hue: ["59,91,255", "120,70,255"],
  audio: "wt-ask.wav",
  drops: [[1280, 1440]],
};

export { EXPO_OUT };
