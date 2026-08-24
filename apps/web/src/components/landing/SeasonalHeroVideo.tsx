'use client';

import { useSeasonalHeroVideo } from '@/lib/hooks/useSeasonalHeroVideo';

// Hari Merdeka / Hari Malaysia hero media — a muted YouTube embed looping
// the 12:00 mark of the referenced parade footage, seasonal-gated to the
// same Aug 25-Sep 20 window as SeasonalBanner (lib/seasonal-window.ts).
//
// Lives in its own framed panel (the hero's right column on wide
// viewports — see LandingClient's two-panel layout, active only when this
// component is), not as a full-bleed background behind the headline
// anymore: a page-wide wash was the only way to keep the footage from
// fighting hero copy for legibility at any real visibility, which capped
// it at a near-invisible opacity-15. Framing it as its own media block
// lets it actually read as video (opacity-50, contrast-125, saturate-125)
// while the copy gets its own high-contrast surfaces instead (see
// LandingClient) — apple-design §12: material weight/depth comes from
// giving each layer its own bounded surface, not one overlay doing both
// jobs.
//
// No `end` param: this loops start->natural-end->restart at `start` via
// the `loop=1&playlist=<id>` combination YouTube's embed API expects for
// single-video looping, rather than a hard-cut at a fixed end second —
// a hand-picked 10-second end point produced a visible jump-cut every
// loop; letting YouTube's own loop mechanism restart at `start` instead
// reads as a smoother, more intentional ambient loop.
//
// prefers-reduced-motion: reduce swaps the iframe for a static frame. We
// can't extract the exact 12:00 video frame ourselves, so this uses
// YouTube's own thumbnail CDN image as an honest substitute — a real frame
// from the same video, not necessarily that exact second.
const VIDEO_ID = 'XmjCOYNtUo8';
const START_SECONDS = 720; // 12:00
const EMBED_SRC =
  `https://www.youtube.com/embed/${VIDEO_ID}?start=${START_SECONDS}` +
  `&autoplay=1&mute=1&loop=1&playlist=${VIDEO_ID}&controls=0&modestbranding=1&playsinline=1&rel=0`;
const STATIC_FRAME_SRC = `https://img.youtube.com/vi/${VIDEO_ID}/hqdefault.jpg`;

export function SeasonalHeroVideo() {
  const { active, reducedMotion } = useSeasonalHeroVideo();

  if (!active) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none relative aspect-[4/3] lg:aspect-square w-full overflow-hidden rounded-[2rem] bg-[#12151C] shadow-[0_24px_60px_-20px_rgba(0,0,0,0.6)] ring-1 ring-white/10"
    >
      {reducedMotion ? (
        <div
          className="absolute inset-0 bg-cover bg-center opacity-50 contrast-125 saturate-125"
          style={{ backgroundImage: `url(${STATIC_FRAME_SRC})` }}
        />
      ) : (
        <iframe
          className="absolute left-1/2 top-1/2 h-[140%] w-[140%] -translate-x-1/2 -translate-y-1/2 opacity-50 contrast-125 saturate-125"
          src={EMBED_SRC}
          title=""
          tabIndex={-1}
          allow="autoplay; encrypted-media"
        />
      )}
      {/* Localized scrim — confined to this framed panel, not the whole
          hero: a soft bottom-anchored gradient for depth/grounding, since
          the copy no longer sits on top of the footage and doesn't need
          protecting from it. */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#12151C]/70 via-transparent to-[#12151C]/20" />
      <div className="absolute inset-0 rounded-[2rem] ring-1 ring-inset ring-white/5" />
    </div>
  );
}
