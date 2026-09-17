import {
  AbsoluteFill,
  Easing,
  Interactive,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Composition } from "remotion";

// NakTahu hero loop — brand-forward, NOT seasonal/flag-themed (this
// replaces the removed Merdeka YouTube embed with an on-brand asset that
// works year-round). Visual language matches the live product exactly:
// --nk-official/#3B6FE0 + --brand-blue/#3B5BFF, --nk-heritage/#E08D5B,
// the dark hero surface #12151C (LandingClient's own heroSurface tone),
// the civic dot-grid + breathing radial fields (ChatAmbientMesh), the
// "Hibiscus-Notch" brand mark (NakTahuMark.tsx: speech-bubble + bunga
// raya), and three REAL agency abbreviations already used in
// AgencyTrustGrid.tsx (LHDN/KWSP/JPN) as small citation-chip motifs —
// never fabricated agency names.

const OFFICIAL = "#3B6FE0";
const BRAND_BLUE = "#3B5BFF";
const HERITAGE = "#E08D5B";
const BG = "#12151C";

const FPS = 30;
// Total loop length. Entrance -> hold -> fade-to-black-for-restart, so
// <video loop> restarting at frame 0 each cycle reads as a deliberate
// "breathe in, hold, breathe out" pulse rather than needing a seamless
// mid-motion splice — the simplest robust way to loop an assembling
// animation. ~0.125Hz cycle (8s), well clear of apple-design's "avoid
// oscillations near 0.2Hz" guidance for full-viewport ambient motion.
const DURATION = 8 * FPS; // 240

function springPop(frame: number, start: number, duration = 18) {
  return interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.spring({ damping: 12, mass: 0.7 }),
  });
}

function DotGrid({ opacity }: { opacity: number }) {
  return (
    <AbsoluteFill
      style={{
        opacity,
        backgroundImage:
          `linear-gradient(to right, ${OFFICIAL}22 1px, transparent 1px), ` +
          `linear-gradient(to bottom, ${OFFICIAL}22 1px, transparent 1px)`,
        backgroundSize: "56px 56px",
      }}
    />
  );
}

/** Two slow-breathing radial glow fields — same treatment as
 * LandingClient's own ambient blobs, so the video reads as one material
 * with the page it sits on, not a separate decorative layer. */
function GlowFields({ frame }: { frame: number }) {
  const t = frame / DURATION;
  const breathe = Math.sin(t * Math.PI * 2); // one full cycle per loop
  return (
    <>
      <AbsoluteFill
        style={{
          background: `radial-gradient(closest-side, ${BRAND_BLUE}33, transparent 70%)`,
          transform: `translate(${-6 + breathe * 3}%, ${-8 - breathe * 2}%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(closest-side, ${HERITAGE}26, transparent 65%)`,
          transform: `translate(${18 - breathe * 4}%, ${10 + breathe * 3}%)`,
        }}
      />
    </>
  );
}

/** The Hibiscus-Notch mark, assembling: bubble materializes, tail draws,
 * five petals bloom in a staggered spring, stamen pops last. Byte-shape
 * identical to NakTahuMark.tsx's default (non-seasonal) SVG paths. */
function BrandMark({ frame }: { frame: number }) {
  const bubble = springPop(frame, 0, 22);
  const tail = springPop(frame, 14, 16);
  const petalStagger = 6;
  const idle = 1 + Math.sin((frame / DURATION) * Math.PI * 2) * 0.015;

  return (
    <Interactive.Div
      name="BrandMark"
      style={{ scale: bubble * idle, opacity: bubble }}
    >
      <svg viewBox="0 0 120 120" width={340} height={340}>
        <rect x="14" y="14" width="92" height="74" rx="30" fill={BRAND_BLUE} />
        <path
          d="M32 88 L32 108 L52 88 Z"
          fill={BRAND_BLUE}
          style={{ opacity: tail }}
        />
        <g>
          {[0, 72, 144, 216, 288].map((rot, i) => {
            const p = springPop(frame, 30 + i * petalStagger, 16);
            return (
              <ellipse
                key={rot}
                cx={98}
                cy={17}
                rx="6.5"
                ry="9"
                fill="#ED1C24"
                transform={`rotate(${rot} 98 26)`}
                style={{ scale: p, opacity: p, transformOrigin: "98px 26px" }}
              />
            );
          })}
          {(() => {
            const stamen = springPop(frame, 30 + 5 * petalStagger, 14);
            return (
              <>
                <circle cx={98} cy={26} r="3" fill="#C4141A" style={{ opacity: stamen }} />
                <line
                  x1={98}
                  y1={26}
                  x2={108}
                  y2={13}
                  stroke="#C4141A"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  style={{ opacity: stamen }}
                />
                <circle cx={108} cy={13} r="1.8" fill="#FFCC00" style={{ opacity: stamen }} />
              </>
            );
          })()}
        </g>
      </svg>
    </Interactive.Div>
  );
}

/** Three small citation-chip motifs — same double-border stamp language as
 * the real CitationChip.tsx, holding the three real agency abbreviations
 * AgencyTrustGrid.tsx already uses. Not fabricated content: these are
 * agencies this product genuinely cites. */
function CitationChips({ frame }: { frame: number }) {
  const chips = [
    { label: "LHDN", start: 108 },
    { label: "KWSP", start: 122 },
    { label: "JPN", start: 136 },
  ];
  return (
    <div style={{ display: "flex", gap: 18, marginTop: 40 }}>
      {chips.map((c, i) => {
        const p = springPop(frame, c.start, 20);
        const float = Math.sin((frame - c.start) / 26) * 4;
        return (
          <div
            key={c.label}
            style={{
              opacity: p,
              scale: p,
              translate: `0px ${float}px`,
              border: `2px double ${OFFICIAL}`,
              background: `${OFFICIAL}1a`,
              color: "#BFD1FF",
              borderRadius: 10,
              padding: "8px 18px",
              fontFamily: "ui-monospace, 'SF Mono', 'Courier New', monospace",
              fontWeight: 700,
              fontSize: 22,
              letterSpacing: "0.02em",
            }}
          >
            {c.label}
          </div>
        );
      })}
    </div>
  );
}

export const NakTahuHero: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Whole-scene fade in at the very start and fade to black at the very
  // end, so a <video loop> restart reads as a clean cut, never a jump.
  const sceneFadeIn = interpolate(frame, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const sceneFadeOut = interpolate(
    frame,
    [durationInFrames - 26, durationInFrames - 2],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) },
  );
  const sceneOpacity = Math.min(sceneFadeIn, sceneFadeOut);

  return (
    <AbsoluteFill style={{ backgroundColor: BG, opacity: sceneOpacity }}>
      <GlowFields frame={frame} />
      <DotGrid opacity={0.5} />
      <AbsoluteFill
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <BrandMark frame={frame} />
        <CitationChips frame={frame} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const RemotionCompositionDefinition: React.FC = () => (
  <Composition
    id="NakTahuHero"
    component={NakTahuHero}
    durationInFrames={DURATION}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
