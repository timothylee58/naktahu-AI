'use client';

import { useRef, useState } from 'react';
import { useSeasonalHeroVideo } from '@/lib/hooks/useSeasonalHeroVideo';
import { useI18n } from '@/lib/i18n';

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
// `enablejsapi=1` + postMessage below is what makes the mute/pause
// buttons real controls, not decoration — the embed still starts muted
// (required for autoplay to work in any browser regardless of this),
// but a visitor can now actually unmute/pause it, which the previous
// pointer-events-none/aria-hidden version never allowed.
//
// prefers-reduced-motion: reduce swaps the iframe for a static frame (no
// mute/pause controls in that case — there's nothing playing to control).
// We can't extract the exact 12:00 video frame ourselves, so this uses
// YouTube's own thumbnail CDN image as an honest substitute — a real
// frame from the same video, not necessarily that exact second.
const VIDEO_ID = 'XmjCOYNtUo8';
const START_SECONDS = 720; // 12:00
const EMBED_SRC =
  `https://www.youtube.com/embed/${VIDEO_ID}?start=${START_SECONDS}` +
  `&autoplay=1&mute=1&loop=1&playlist=${VIDEO_ID}&controls=0&modestbranding=1&playsinline=1&rel=0&enablejsapi=1`;
const STATIC_FRAME_SRC = `https://img.youtube.com/vi/${VIDEO_ID}/hqdefault.jpg`;

function postPlayerCommand(iframe: HTMLIFrameElement | null, func: string) {
  iframe?.contentWindow?.postMessage(JSON.stringify({ event: 'command', func, args: [] }), '*');
}

export function SeasonalHeroVideo() {
  const { active, reducedMotion, milestone } = useSeasonalHeroVideo();
  const { t } = useI18n();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [muted, setMuted] = useState(true);
  const [paused, setPaused] = useState(false);

  if (!active) return null;

  const caption = (() => {
    switch (milestone.kind) {
      case 'before_merdeka':
        return t('landing.hero.countdown.before_merdeka').replace('{days}', String(milestone.days));
      case 'merdeka_day':
        return t('landing.hero.countdown.merdeka_day');
      case 'before_malaysia_day':
        return t('landing.hero.countdown.before_malaysia_day').replace('{days}', String(milestone.days));
      case 'malaysia_day':
        return t('landing.hero.countdown.malaysia_day');
      default:
        return t('landing.hero.video_caption');
    }
  })();

  const toggleMute = () => {
    postPlayerCommand(iframeRef.current, muted ? 'unMute' : 'mute');
    setMuted((m) => !m);
  };
  const togglePause = () => {
    postPlayerCommand(iframeRef.current, paused ? 'playVideo' : 'pauseVideo');
    setPaused((p) => !p);
  };

  return (
    <div className="relative aspect-[4/3] lg:aspect-square w-full overflow-hidden rounded-[2rem] bg-[#12151C] shadow-[0_24px_60px_-20px_rgba(0,0,0,0.6)] ring-1 ring-white/10">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        {reducedMotion ? (
          <div
            className="absolute inset-0 bg-cover bg-center opacity-50 contrast-125 saturate-125"
            style={{ backgroundImage: `url(${STATIC_FRAME_SRC})` }}
          />
        ) : (
          <iframe
            ref={iframeRef}
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
            protecting from it. Also what keeps the caption chip and the
            mute/pause controls legible against the footage. */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#12151C]/70 via-transparent to-[#12151C]/20" />
        <div className="absolute inset-0 rounded-[2rem] ring-1 ring-inset ring-white/5" />
      </div>

      {/* Caption chip — a live countdown to Merdeka/Malaysia Day (or the
          day-of greeting once it arrives) instead of a static label, and
          ties the footage to the occasion it's actually celebrating. The
          flag emoji mirrors the one already in the hero badge above the
          headline (🇲🇾 {t('landing.badge')}). */}
      <div className="absolute bottom-4 left-4 inline-flex items-center gap-1.5 rounded-full bg-[#12151C]/80 backdrop-blur-sm ring-1 ring-white/10 px-3 py-1.5 text-xs font-semibold text-white locale-nowrap">
        <span aria-hidden>🇲🇾</span>
        {caption}
      </div>

      {/* Mute/pause — the only real interaction this panel offers now
          that it isn't a page background any more. Not shown for the
          reduced-motion static-frame path (nothing is playing). */}
      {!reducedMotion && (
        <div className="absolute bottom-4 right-4 flex items-center gap-1.5">
          <button
            type="button"
            onClick={togglePause}
            aria-label={paused ? t('landing.hero.video_play') : t('landing.hero.video_pause')}
            title={paused ? t('landing.hero.video_play') : t('landing.hero.video_pause')}
            className="flex items-center justify-center w-8 h-8 rounded-full bg-[#12151C]/80 backdrop-blur-sm ring-1 ring-white/10 text-white hover:bg-[#12151C]/95 transition-colors"
          >
            {paused ? (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M6.3 2.841A1.5 1.5 0 0 0 4 4.11v11.78a1.5 1.5 0 0 0 2.3 1.269l9.344-5.89a1.5 1.5 0 0 0 0-2.538L6.3 2.841Z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                <path fillRule="evenodd" d="M6.75 5.5a.75.75 0 0 1 .75.75v7.5a.75.75 0 0 1-1.5 0v-7.5a.75.75 0 0 1 .75-.75Zm6.5 0a.75.75 0 0 1 .75.75v7.5a.75.75 0 0 1-1.5 0v-7.5a.75.75 0 0 1 .75-.75Z" clipRule="evenodd" />
              </svg>
            )}
          </button>
          <button
            type="button"
            onClick={toggleMute}
            aria-label={muted ? t('landing.hero.video_unmute') : t('landing.hero.video_mute')}
            title={muted ? t('landing.hero.video_unmute') : t('landing.hero.video_mute')}
            className="flex items-center justify-center w-8 h-8 rounded-full bg-[#12151C]/80 backdrop-blur-sm ring-1 ring-white/10 text-white hover:bg-[#12151C]/95 transition-colors"
          >
            {muted ? (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M10 3.75a.75.75 0 0 0-1.264-.546L4.703 7H3.167a.75.75 0 0 0-.75.75v4.5c0 .414.336.75.75.75h1.536l4.033 3.796A.75.75 0 0 0 10 16.25V3.75Z" />
                <path fillRule="evenodd" d="M12.72 7.22a.75.75 0 0 1 1.06 0L15 8.44l1.22-1.22a.75.75 0 1 1 1.06 1.06L16.06 9.5l1.22 1.22a.75.75 0 1 1-1.06 1.06L15 10.56l-1.22 1.22a.75.75 0 1 1-1.06-1.06l1.22-1.22-1.22-1.22a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M10 3.75a.75.75 0 0 0-1.264-.546L4.703 7H3.167a.75.75 0 0 0-.75.75v4.5c0 .414.336.75.75.75h1.536l4.033 3.796A.75.75 0 0 0 10 16.25V3.75Z" />
                <path d="M15.95 5.05a.75.75 0 1 0-1.06 1.06 5.5 5.5 0 0 1 0 7.78.75.75 0 1 0 1.06 1.06 7 7 0 0 0 0-9.9ZM13.829 7.172a.75.75 0 1 0-1.061 1.06 2.5 2.5 0 0 1 0 3.536.75.75 0 1 0 1.06 1.06 4 4 0 0 0 0-5.656Z" />
              </svg>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
