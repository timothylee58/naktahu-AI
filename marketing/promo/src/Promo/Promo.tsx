import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { Audio } from "@remotion/media";
import { TransitionSeries, linearTiming, springTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { Finish, Stage } from "./Shared";
import { S1Chaos } from "./S1Chaos";
import { S2Logo } from "./S2Logo";
import { S3Demo } from "./S3Demo";
import { S4Agents } from "./S4Agents";
import { S5Trust } from "./S5Trust";
import { S6End } from "./S6End";

export const Promo: React.FC = () => {
  return (
    <AbsoluteFill>
      <Stage />
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={92} name="Chaos">
          <S1Chaos />
        </TransitionSeries.Sequence>
        <TransitionSeries.Sequence durationInFrames={116} name="Logo">
          <S2Logo />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 10 })} />
        <TransitionSeries.Sequence durationInFrames={170} name="Demo">
          <S3Demo />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-right" })} timing={springTiming({ config: { damping: 200 }, durationInFrames: 22 })} />
        <TransitionSeries.Sequence durationInFrames={110} name="Agents">
          <S4Agents />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 16 })} />
        <TransitionSeries.Sequence durationInFrames={92} name="Trust">
          <S5Trust />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={linearTiming({ durationInFrames: 16 })} />
        <TransitionSeries.Sequence durationInFrames={84} name="End">
          <S6End />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      <Finish />
      <Audio src={staticFile("score.wav")} name="Score" />
    </AbsoluteFill>
  );
};
