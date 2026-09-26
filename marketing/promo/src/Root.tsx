import "./index.css";
import { Composition, Folder } from "remotion";
import { Promo } from "./Promo/Promo";
import { S1Chaos } from "./Promo/S1Chaos";
import { S2Logo } from "./Promo/S2Logo";
import { S3Demo } from "./Promo/S3Demo";
import { S4Agents } from "./Promo/S4Agents";
import { S5Trust } from "./Promo/S5Trust";
import { S6End } from "./Promo/S6End";
import { Showcase } from "./Showcase/Showcase";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Folder name="Promo-Scenes">
        <Composition id="S1Chaos" component={S1Chaos} durationInFrames={92} fps={30} width={1920} height={1080} />
        <Composition id="S2Logo" component={S2Logo} durationInFrames={116} fps={30} width={1920} height={1080} />
        <Composition id="S3Demo" component={S3Demo} durationInFrames={170} fps={30} width={1920} height={1080} />
        <Composition id="S4Agents" component={S4Agents} durationInFrames={110} fps={30} width={1920} height={1080} />
        <Composition id="S5Trust" component={S5Trust} durationInFrames={92} fps={30} width={1920} height={1080} />
        <Composition id="S6End" component={S6End} durationInFrames={84} fps={30} width={1920} height={1080} />
      </Folder>
      <Folder name="Showcase">
        <Composition id="Showcase-bm-16x9" component={Showcase} durationInFrames={1696} fps={30} width={1920} height={1080} defaultProps={{ lang: "bm" }} />
        <Composition id="Showcase-bm-9x16" component={Showcase} durationInFrames={1696} fps={30} width={1080} height={1920} defaultProps={{ lang: "bm" }} />
        <Composition id="Showcase-en-16x9" component={Showcase} durationInFrames={1696} fps={30} width={1920} height={1080} defaultProps={{ lang: "en" }} />
        <Composition id="Showcase-en-9x16" component={Showcase} durationInFrames={1696} fps={30} width={1080} height={1920} defaultProps={{ lang: "en" }} />
        <Composition id="Showcase-zh-16x9" component={Showcase} durationInFrames={1696} fps={30} width={1920} height={1080} defaultProps={{ lang: "zh" }} />
        <Composition id="Showcase-zh-9x16" component={Showcase} durationInFrames={1696} fps={30} width={1080} height={1920} defaultProps={{ lang: "zh" }} />
      </Folder>
      <Composition id="NaktahuPromo" component={Promo} durationInFrames={600} fps={30} width={1920} height={1080} />
    </>
  );
};
