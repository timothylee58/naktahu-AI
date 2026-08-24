'use client';

import { useEffect, useState } from 'react';
import { inSeasonalWindow } from '@/lib/seasonal-window';

// Hari Merdeka / Hari Malaysia hero backdrop — a muted YouTube embed looping
// the 12:00-12:10 mark of the referenced parade footage, seasonal-gated to
// the same Aug 25-Sep 20 window as SeasonalBanner (lib/seasonal-window.ts).
//
// Scoped to the hero section only (apple-design §14/§16: avoid full-viewport
// moving backgrounds; restraint over spectacle) — this sits behind the
// hero's own two-tone glow + copy, not the whole page, and never plays audio
// (muted is also required for autoplay to work in any browser regardless).
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
  const [active, setActive] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    // Client-only check, same pattern as SeasonalBanner — avoids an
    // SSR/client hydration mismatch on both the date window and the media
    // query (this session has already hit that exact class of bug twice).
    setActive(inSeasonalWindow(new Date()));
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  if (!active) return null;

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden rounded-b-[2.5rem]">
      {reducedMotion ? (
        <div
          className="absolute inset-0 bg-cover bg-center opacity-25"
          style={{ backgroundImage: `url(${STATIC_FRAME_SRC})` }}
        />
      ) : (
        <iframe
          className="absolute left-1/2 top-1/2 h-[130%] w-[130%] -translate-x-1/2 -translate-y-1/2 opacity-25"
          src={EMBED_SRC}
          title=""
          tabIndex={-1}
          allow="autoplay; encrypted-media"
        />
      )}
      {/* Scrim so hero copy stays legible over the footage — dark mode needs
          a heavier overlay since the video brightness competes with white/blue
          text on the dark background. 90% top fading to full opaque bottom. */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#12151C]/80 via-[#12151C]/85 to-[#12151C] dark:from-[#12151C]/80 dark:via-[#12151C]/85 dark:to-[#12151C]" />
    </div>
  );
}
