import React from "react";
import { AbsoluteFill, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Audio } from "@remotion/media";
import { BAR, BEAT, C, Feature, beatPulse, clamp, display, mono, useLayout } from "./core";
import { AnswerMock, ChatMock, ShareMock, TranslateMock, VerifiedMock, VoiceMock } from "./mocksChat";
import { ApiMock, DraftMock, GrantMock, HubMock, ImmigrationMock, MoreMock, StudyMock, TriageMock, WarungMock } from "./mocksAgents";
import { EndCard, Hook, Loading, LogoDrop, PricingMock } from "./bookends";
import { Mark } from "../Promo/Mark";
import { Finish } from "../Promo/Shared";
import type { CopyKey } from "./copy.bm";
import { type Lang, LangProvider, useT } from "./i18n";

type F = { bar: number; kicker: string; chunks: CopyKey[]; at?: number[]; accent?: number[]; sub?: CopyKey; mock: React.FC };

const B = BEAT;
export const FEATURES: F[] = [
  { bar: 3, kicker: "ANSWER ENGINE", chunks: ["f3.h0", "f3.h1"], at: [0, B], accent: [1], sub: "f3.sub", mock: ChatMock },
  { bar: 4, kicker: "CITED ANSWERS", chunks: ["f4.h0", "f4.h1"], at: [0, B], accent: [1], sub: "f4.sub", mock: AnswerMock },
  { bar: 5, kicker: "VERIFIED SOURCES", chunks: ["f5.h0", "f5.h1", "f5.h2"], at: [0, B, B * 2], accent: [1], mock: VerifiedMock },
  { bar: 6, kicker: "TRILINGUAL", chunks: [], at: [0, B, B * 2], accent: [2], sub: "f6.sub", mock: TranslateMock },
  { bar: 7, kicker: "VOICE INPUT", chunks: ["f7.h0", "f7.h1"], at: [0, B], accent: [1], sub: "f7.sub", mock: VoiceMock },
  { bar: 8, kicker: "SHARE", chunks: ["f8.h0", "f8.h1"], at: [0, B], accent: [1], sub: "f8.sub", mock: ShareMock },
  { bar: 9, kicker: "12 AI AGENTS", chunks: ["f9.h0", "f9.h1"], at: [0, B + 7], accent: [1], sub: "f9.sub", mock: HubMock },
  { bar: 10, kicker: "GRANT FINDER", chunks: ["f10.h0", "f10.h1"], at: [0, B], accent: [1], sub: "f10.sub", mock: GrantMock },
  { bar: 11, kicker: "GRANT DRAFT GENERATOR", chunks: ["f11.h0", "f11.h1"], at: [0, B], accent: [1], sub: "f11.sub", mock: DraftMock },
  { bar: 12, kicker: "HEALTH TRIAGE", chunks: ["f12.h0", "f12.h1"], at: [0, B], accent: [1], sub: "f12.sub", mock: TriageMock },
  { bar: 13, kicker: "IMMIGRATION NAVIGATOR", chunks: ["f13.h0", "f13.h1"], at: [0, B], accent: [1], sub: "f13.sub", mock: ImmigrationMock },
  { bar: 14, kicker: "STUDY AGENT", chunks: ["f14.h0", "f14.h1"], at: [0, B], accent: [1], sub: "f14.sub", mock: StudyMock },
  { bar: 15, kicker: "WARUNG WATCH", chunks: ["f15.h0", "f15.h1"], at: [0, B], accent: [1], sub: "f15.sub", mock: WarungMock },
  { bar: 16, kicker: "AND MORE", chunks: ["f16.h0", "f16.h1"], at: [0, B], accent: [1], sub: "f16.sub", mock: MoreMock },
  { bar: 17, kicker: "DEVELOPER API", chunks: ["f17.h0", "f17.h1"], at: [0, B], accent: [1], sub: "f17.sub", mock: ApiMock },
  { bar: 18, kicker: "PRICING", chunks: ["f18.h0", "f18.h1"], at: [0, B], accent: [1], mock: PricingMock },
];
/** The trilingual headline is the language names themselves, identical in every cut. */
const TRILINGUAL = ["BM.", "English.", "中文."];
const COUNTED = FEATURES.filter((f) => f.bar <= 17);

/** Kicks sound in bars 1-8, 10-16, 17 (beats 1-3) and 18: flash the stage on each one. */
const kickOn = (frame: number) => {
  const bar = Math.floor(frame / BAR);
  const beat = Math.floor((frame % BAR) / BEAT);
  if (bar === 1) return 0.4;
  if ((bar >= 2 && bar <= 8) || (bar >= 10 && bar <= 16) || bar === 18) return 1;
  if (bar === 17 && beat < 3) return 1;
  return 0;
};

const Backdrop: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / 30;
  const k = kickOn(frame) * beatPulse(frame);
  return (
    <AbsoluteFill style={{ backgroundColor: C.bg, overflow: "hidden" }}>
      <AbsoluteFill style={{ background: `radial-gradient(1000px 800px at ${35 + Math.sin(t * 0.6) * 12}% ${30 + Math.cos(t * 0.5) * 10}%, rgba(59,91,255,${0.26 + k * 0.1}), transparent 70%)` }} />
      <AbsoluteFill style={{ background: `radial-gradient(800px 700px at ${72 + Math.cos(t * 0.45) * 12}% ${70 + Math.sin(t * 0.5) * 10}%, rgba(120,70,255,${0.16 + k * 0.06}), transparent 70%)` }} />
      <AbsoluteFill style={{ background: `radial-gradient(560px 460px at ${80 + Math.sin(t * 0.7) * 8}% ${16 + Math.cos(t * 0.6) * 6}%, rgba(255,178,56,0.08), transparent 70%)` }} />
      <AbsoluteFill
        style={{
          backgroundImage: "radial-gradient(rgba(170,185,255,0.17) 1.3px, transparent 1.5px)",
          backgroundSize: "46px 46px",
          backgroundPosition: `${(frame * 0.6) % 46}px ${(frame * 0.35) % 46}px`,
          maskImage: "radial-gradient(ellipse 75% 65% at 50% 50%, black 15%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse 75% 65% at 50% 50%, black 15%, transparent 80%)",
          opacity: 0.7 + k * 0.5,
        }}
      />
      <AbsoluteFill style={{ background: `radial-gradient(ellipse 60% 50% at 50% 50%, rgba(123,145,255,${k * 0.1}), transparent 70%)` }} />
    </AbsoluteFill>
  );
};

const Hud: React.FC = () => {
  const frame = useCurrentFrame();
  const L = useLayout();
  const bar = Math.floor(frame / BAR);
  const idx = COUNTED.findIndex((f) => f.bar === bar);
  const vis = interpolate(frame, [3 * BAR - 4, 3 * BAR + 6, 18 * BAR - 6, 18 * BAR], [0, 1, 1, 0], clamp);
  if (vis <= 0) return null;
  const within = (frame % BAR) / BAR;
  const top = L.v ? 172 : 46;
  const barY = L.v ? 1566 : 1016;
  const x0 = L.v ? 80 : 110;
  const x1 = L.v ? L.W - 80 : L.W - 110;
  const seg = (x1 - x0 - (COUNTED.length - 1) * 8) / COUNTED.length;
  return (
    <AbsoluteFill style={{ opacity: vis, pointerEvents: "none" }}>
      <div style={{ position: "absolute", left: x0, top, display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 46, height: 46 }}>
          <Mark frame={200} size={46} bubbleAt={0} bloomAt={0} id="hud" />
        </div>
        <span style={{ fontFamily: display, fontWeight: 800, fontSize: 32, letterSpacing: "-0.03em", color: C.white }}>
          naktahu<span style={{ color: C.blue }}>.my</span>
        </span>
      </div>
      {idx >= 0 && (
        <div style={{ position: "absolute", right: L.W - x1, top: top + 4, fontFamily: mono, fontSize: 30, fontWeight: 500, color: C.white, letterSpacing: "0.06em" }}>
          <span style={{ color: C.amber }}>{String(idx + 1).padStart(2, "0")}</span>
          <span style={{ color: C.mute }}> / {COUNTED.length}</span>
        </div>
      )}
      <div style={{ position: "absolute", left: x0, top: barY, display: "flex", gap: 8 }}>
        {COUNTED.map((f, i) => {
          const fill = i < idx ? 1 : i === idx ? within : 0;
          return (
            <div key={f.bar} style={{ width: seg, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.13)", overflow: "hidden" }}>
              <div style={{ width: `${fill * 100}%`, height: 6, background: i === idx ? C.amber : C.blueHi }} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const FeatureScene: React.FC<{ f: F; i: number }> = ({ f, i }) => {
  const t = useT();
  const L = useLayout();
  const Mock = f.mock;
  const trilingual = f.bar === 6;
  return (
    <Feature
      kicker={f.kicker}
      chunks={trilingual ? TRILINGUAL : f.chunks.map(t)}
      at={f.at}
      accent={f.accent}
      sub={f.sub && t(f.sub)}
      dir={i % 2 ? -1 : 1}
      // three stacked lines plus a subtitle outgrow the 9:16 headline slot
      inline={trilingual && L.v}
    >
      <Mock />
    </Feature>
  );
};

export const Showcase: React.FC<{ lang: Lang }> = ({ lang }) => {
  return (
    <LangProvider lang={lang}>
    <AbsoluteFill>
      <Backdrop />
      <Sequence from={0} durationInFrames={BAR} name="Hook">
        <Hook />
      </Sequence>
      <Sequence from={BAR} durationInFrames={BAR} name="Loading">
        <Loading />
      </Sequence>
      <Sequence from={BAR * 2} durationInFrames={BAR} name="Logo drop">
        <LogoDrop />
      </Sequence>
      {FEATURES.map((f, i) => (
        <Sequence key={f.bar} from={f.bar * BAR} durationInFrames={BAR} name={f.kicker}>
          <FeatureScene f={f} i={i} />
        </Sequence>
      ))}
      <Sequence from={BAR * 19} durationInFrames={76} name="End card">
        <EndCard />
      </Sequence>
      <Hud />
      <Finish />
      <Audio src={staticFile("showcase.wav")} name="Score" />
    </AbsoluteFill>
    </LangProvider>
  );
};
