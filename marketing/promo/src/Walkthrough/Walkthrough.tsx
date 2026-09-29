import React from "react";
import { AbsoluteFill, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Audio } from "@remotion/media";
import { Mark } from "../Promo/Mark";
import { Finish } from "../Promo/Shared";
import { EndCard } from "../Showcase/bookends";
import { Slam } from "../Showcase/core";
import { LangProvider } from "../Showcase/i18n";
import { type WLang, WLangProvider, useW } from "./i18n";
import { WALKTHROUGHS } from "./scripts";
import { CH0, CH_DUR, END, HOOK, RECAP, TITLE } from "./timeline";
import {
  BAR,
  BEAT,
  Backdrop,
  C,
  Callout,
  Camera,
  type CamKey,
  Caption,
  ChapterCard,
  Cursor,
  type CurKey,
  EXPO_IN,
  Hud,
  Landscape,
  Spotlight,
  clamp,
  display,
  mono,
  prog,
} from "./engine";


export type Chapter = {
  name: string;
  title: string;
  line: string;
  cam: CamKey[];
  cursor?: CurKey[];
  callouts?: { f: number; to: number; x: number; y: number; text: string; side?: "left" | "right" | "top" | "bottom"; color?: string }[];
  spots?: { f: number; to: number; x: number; y: number; w: number; h: number; r?: number }[];
  captions: { f: number; to: number; text: string; detail?: string }[];
  /** The filmed screen: app-space content (AppShell etc.), given the chapter-local frame. */
  Screen: React.FC;
};

export type Script = {
  id: string;
  series: string;
  number: string;
  name: string;
  tagline: string;
  hook: { lines: string[]; accent: number; chaos: string[] };
  chapters: Chapter[];
  recap: { lines: string[]; plan: string; planDetail: string };
  hue: [string, string];
  audio: string;
  drops: [number, number][];
};

/** Bars 0-1: the problem, as a cloud of open tabs, answered by a two-beat slam. */
const Hook: React.FC<{ s: Script }> = ({ s }) => {
  const frame = useCurrentFrame();
  const t = useW();
  const { width: W, height: H } = useVideoConfig();
  const v = H > W;
  const out = prog(frame, HOOK.dur - 8, 8, EXPO_IN);
  const collapse = prog(frame, BAR - 6, 18);
  return (
    <AbsoluteFill style={{ opacity: 1 - out, filter: `blur(${out * 12}px)` }}>
      {s.hook.chaos.map((tab, i) => {
        const a = (i * 137.5 * Math.PI) / 180;
        const r = 300 + (i % 3) * 120;
        const x = W / 2 + Math.cos(a) * r * (v ? 0.55 : 1.5);
        const y = H / 2 + Math.sin(a) * r * (v ? 1.9 : 0.75);
        const p = prog(frame, i * 3, 14);
        const drift = Math.sin(frame / 20 + i) * 8;
        return (
          <div
            key={tab}
            style={{
              position: "absolute",
              left: x + (W / 2 - x) * collapse,
              top: y + drift + (H / 2 - y) * collapse,
              translate: "-50% -50%",
              rotate: `${(i % 2 ? 1 : -1) * (3 + (i % 4)) * (1 - collapse)}deg`,
              scale: `${(0.7 + 0.3 * p) * (1 - collapse * 0.9)}`,
              opacity: p * (1 - collapse),
              padding: "16px 26px",
              borderRadius: 16,
              background: "rgba(20,26,66,0.92)",
              border: "1.5px solid rgba(160,175,255,0.25)",
              fontFamily: display,
              fontSize: 26,
              fontWeight: 600,
              color: "rgba(244,246,255,0.85)",
              whiteSpace: "nowrap",
              boxShadow: "0 20px 50px rgba(0,0,0,0.5)",
            }}
          >
            <span style={{ fontFamily: mono, fontSize: 18, color: C.mute, marginRight: 12 }}>tab</span>
            {t(tab)}
          </div>
        );
      })}
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ width: v ? W - 120 : 1600 }}>
          {s.hook.lines.map((l, i) => (
            <Slam key={l} chunks={[t(l)]} at={[BAR + i * BEAT * 2 - (i ? 0 : 4)]} size={v ? 118 : 150} align="center" accent={i === s.hook.accent ? [0] : []} />
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** Bars 2-3: logo drop into the walkthrough title. */
const Title: React.FC<{ s: Script }> = ({ s }) => {
  const frame = useCurrentFrame();
  const t = useW();
  const { width: W, height: H } = useVideoConfig();
  const v = H > W;
  const out = prog(frame, TITLE.dur - 10, 10, EXPO_IN);
  const word = "naktahu.my".split("");
  const line = prog(frame, BEAT * 2, 16);
  const name = prog(frame, BEAT * 3, 18);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 10, fontFamily: display, opacity: 1 - out, scale: `${1 + out * 0.15}`, filter: `blur(${out * 14}px)` }}>
      <div style={{ width: 200, height: 200, marginBottom: 18 }}>
        <Mark frame={frame} size={200} bubbleAt={0} bloomAt={6} id={`title-${s.id}`} />
      </div>
      <div style={{ display: "flex", overflow: "hidden", paddingBottom: 10 }}>
        {word.map((ch, i) => {
          const p = prog(frame, 6 + i * 1.3, 14);
          return (
            <span key={i} style={{ display: "inline-block", fontSize: 120, fontWeight: 800, letterSpacing: "-0.045em", lineHeight: 1.05, color: i >= 7 ? C.blue : C.white, translate: `0 ${(1 - p) * 110}%`, opacity: p }}>
              {ch}
            </span>
          );
        })}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 22, marginTop: 20, opacity: line }}>
        <div style={{ width: 90 * line, height: 2, background: C.amber }} />
        <span style={{ fontFamily: mono, fontSize: 28, letterSpacing: "0.24em", color: C.amber }}>{t("WALKTHROUGH")} {s.number}</span>
        <div style={{ width: 90 * line, height: 2, background: C.amber }} />
      </div>
      <div style={{ fontSize: v ? 84 : 96, maxWidth: W - 120, textAlign: "center", lineHeight: 1.05, fontWeight: 800, letterSpacing: "-0.04em", color: C.white, clipPath: `inset(0 ${(1 - name) * 100}% 0 0)` }}>{t(s.name)}</div>
      <div style={{ fontSize: 36, maxWidth: W - 120, textAlign: "center", fontWeight: 500, color: C.mute, opacity: prog(frame, BEAT * 4, 14) }}>{t(s.tagline)}</div>
    </AbsoluteFill>
  );
};

/** Bars 34-35: three-word recap on the beat, then the plan that gets you started. */
const Recap: React.FC<{ s: Script }> = ({ s }) => {
  const frame = useCurrentFrame();
  const t = useW();
  const { width: W, height: H } = useVideoConfig();
  const v = H > W;
  const out = prog(frame, RECAP.dur - 8, 8, EXPO_IN);
  const card = prog(frame, BAR - 4, 16);
  // fit the one-row recap to the frame: longer translations get a smaller size
  const words = s.recap.lines.map(t);
  const chars = words.reduce((n, w) => n + [...w].reduce((m, c) => m + (/[\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF]/.test(c) ? 1.8 : 1), 0), 0);
  const recapSize = v ? 130 : Math.min(140, Math.floor((W - 260) / (chars * 0.56)));
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 40, opacity: 1 - out, filter: `blur(${out * 10}px)` }}>
      <div style={{ display: "flex", flexDirection: v ? "column" : "row", alignItems: "center", gap: v ? 10 : 56, whiteSpace: "nowrap", translate: `0 ${-card * 60}px` }}>
        {s.recap.lines.map((l, i) => (
          <Slam key={l} chunks={[words[i]]} at={[i * BEAT]} size={recapSize} align={v ? "center" : "left"} accent={i === s.recap.lines.length - 1 ? [0] : []} />
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: v ? "column" : "row", maxWidth: W - 120, textAlign: "center", alignItems: "center", gap: v ? 14 : 28, padding: "30px 44px", borderRadius: 30, background: "rgba(20,26,66,0.85)", border: "1.5px solid rgba(123,145,255,0.45)", boxShadow: "0 30px 80px rgba(0,0,0,0.45), 0 0 90px rgba(59,91,255,0.25)", opacity: card, scale: `${0.85 + 0.15 * card}`, fontFamily: display }}>
        <div style={{ fontFamily: mono, fontSize: 24, letterSpacing: "0.18em", color: C.amber }}>{t(s.recap.plan)}</div>
        {!v && <div style={{ width: 2, height: 46, background: "rgba(160,175,255,0.3)" }} />}
        <div style={{ fontSize: 36, fontWeight: 700, color: C.white }}>{t(s.recap.planDetail)}</div>
      </div>
    </AbsoluteFill>
  );
};

const ChapterScene: React.FC<{ c: Chapter; n: number }> = ({ c, n }) => {
  const frame = useCurrentFrame();
  const t = useW();
  // the whole filmed screen fades up under the chapter card and out at the end
  const vis = Math.min(prog(frame, 0, 10), 1 - prog(frame, CH_DUR - 8, 8, EXPO_IN));
  const Screen = c.Screen;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ opacity: vis }}>
        <Landscape>
          <Camera keys={c.cam}>
            <Screen />
            {c.spots?.map((s) => <Spotlight key={`${s.f}-${s.x}`} {...s} from={s.f} />)}
            {c.callouts?.map((k) => <Callout key={`${k.f}-${k.text}`} {...k} text={t(k.text)} from={k.f} />)}
            {c.cursor && <Cursor keys={c.cursor} />}
          </Camera>
        </Landscape>
      </AbsoluteFill>
      {c.captions.map((k) => (
        <Caption key={k.f} from={k.f} to={k.to} text={t(k.text)} detail={k.detail && t(k.detail)} />
      ))}
      <ChapterCard n={n} title={t(c.title)} line={t(c.line)} />
    </AbsoluteFill>
  );
};

/** Looked up by id: composition props are JSON-serialised, which would drop each chapter's Screen component. */
export const Walkthrough: React.FC<{ id: string; lang: WLang }> = ({ id, lang }) => (
  <WLangProvider lang={lang}>
    <LangProvider lang={lang}>
      <WalkthroughBody id={id} />
    </LangProvider>
  </WLangProvider>
);

const WalkthroughBody: React.FC<{ id: string }> = ({ id }) => {
  const t = useW();
  const s = WALKTHROUGHS.find((w) => w.id === id)!;
  const drums = (f: number) => f >= 2 * BAR && f < END.from && !s.drops.some(([a, b]) => f >= a && f < b);
  const chapters = s.chapters.map((c, i) => ({ name: t(c.name), from: CH0 + i * CH_DUR, to: CH0 + (i + 1) * CH_DUR }));
  return (
      <AbsoluteFill>
        <Backdrop hue={s.hue} drums={drums} />
        <Sequence from={HOOK.from} durationInFrames={HOOK.dur} name="Hook">
          <Hook s={s} />
        </Sequence>
        <Sequence from={TITLE.from} durationInFrames={TITLE.dur} name="Title">
          <Title s={s} />
        </Sequence>
        {s.chapters.map((c, i) => (
          <Sequence key={c.name} from={CH0 + i * CH_DUR} durationInFrames={CH_DUR} name={`${i + 1} ${c.name}`}>
            <ChapterScene c={c} n={i + 1} />
          </Sequence>
        ))}
        <Sequence from={RECAP.from} durationInFrames={RECAP.dur} name="Recap">
          <Recap s={s} />
        </Sequence>
        <Sequence from={END.from} durationInFrames={END.dur} name="End card">
          <EndCard />
        </Sequence>
        <Hud chapters={chapters} show={[CH0, RECAP.from]} series={t(s.series)} />
        <Finish />
        <Audio src={staticFile(s.audio)} />
      </AbsoluteFill>
  );
};

export { interpolate, clamp };
