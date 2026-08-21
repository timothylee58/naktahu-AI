'use client';

/**
 * "Hibiscus-Notch" — the NakTahu brand mark.
 *
 * A rounded speech bubble (the answer) with a single bunga raya (hibiscus)
 * overlapping its top-right corner — a nod to the national flower without
 * reading as an official government seal, which this product must never
 * imply. Replaces the earlier five-amber-dot pentagon with one flower, per
 * the reference art.
 *
 * Aug25-Sep20 (Merdeka/Hari Malaysia window — lib/seasonal-window.ts):
 * swaps to a "Merdeka Bubble" variant — the Jalur Gemilang clipped flush to
 * the bubble's own silhouette (edge to edge, tail excluded), no white
 * inset frame and no wavy hem — both tried in earlier iterations of this
 * file and removed on user feedback. The star (STAR_14_POINT_PATH) is the
 * real Bintang Persekutuan: 14 points, not a generic 5-point star — the
 * flag's single most identity-bearing detail, so it's the one place this
 * mark doesn't simplify.
 *
 * Client component (useEffect-gated season check) rather than a server-side
 * date check, for the same reason as SeasonalBanner/ChatAmbientMesh/
 * PromptChips elsewhere in this codebase: a server-computed "now" would
 * disagree with the client's on a date-window boundary and trip a
 * hydration mismatch. Renders the default (non-seasonal) mark on the first
 * client render too — identical to SSR — then swaps post-mount if in
 * season, so server and first paint always agree.
 *
 * Inlined as JSX rather than imported from a .svg file: this repo has no
 * @svgr/webpack (or equivalent) configured in next.config.ts, and every other
 * icon here is inline SVG too.
 *
 * Colours resolve from the brand tokens in globals.css, with literal
 * fallbacks so the mark still renders correctly anywhere the cascade does not
 * reach (e.g. an SVG rasterised out of context).
 */
import { useEffect, useState } from 'react';
import { inSeasonalWindow } from '@/lib/seasonal-window';

interface NakTahuMarkProps {
  /** Rendered width and height in px. */
  size?: number;
  className?: string;
  /** Set when the mark sits next to a visible wordmark, so screen readers
   *  do not hear the brand name twice. */
  'aria-hidden'?: boolean;
}

/** Single bunga raya — 5 overlapping petals + stamen, centred on `cx,cy`.
 * Shared between both mark variants so the flower stays byte-identical
 * whichever branch renders it. */
function Hibiscus({ cx, cy }: { cx: number; cy: number }) {
  return (
    <g>
      <g fill="#ED1C24">
        <ellipse cx={cx} cy={cy - 9} rx="6.5" ry="9" transform={`rotate(0 ${cx} ${cy})`} />
        <ellipse cx={cx} cy={cy - 9} rx="6.5" ry="9" transform={`rotate(72 ${cx} ${cy})`} />
        <ellipse cx={cx} cy={cy - 9} rx="6.5" ry="9" transform={`rotate(144 ${cx} ${cy})`} />
        <ellipse cx={cx} cy={cy - 9} rx="6.5" ry="9" transform={`rotate(216 ${cx} ${cy})`} />
        <ellipse cx={cx} cy={cy - 9} rx="6.5" ry="9" transform={`rotate(288 ${cx} ${cy})`} />
      </g>
      <circle cx={cx} cy={cy} r="3" fill="#C4141A" />
      {/* stamen — the long protruding pistil that reads as "hibiscus" rather
          than a generic flower, per the reference art */}
      <line x1={cx} y1={cy} x2={cx + 10} y2={cy - 13} stroke="#C4141A" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx={cx + 10} cy={cy - 13} r="1.8" fill="#FFCC00" />
    </g>
  );
}

// Real 14-point federal star (Bintang Persekutuan) — one point per state +
// federal territories, outer radius 11 / inner radius 4.5, centred at the
// origin. Generated once (28 alternating outer/inner vertices) and pasted
// as a literal so no trig runs at render time.
const STAR_14_POINT_PATH =
  'M0,-11 L1,-4.39 L4.77,-9.91 L2.81,-3.52 L8.6,-6.86 L4.05,-1.95 L10.72,-2.45 L4.5,0 ' +
  'L10.72,2.45 L4.05,1.95 L8.6,6.86 L2.81,3.52 L4.77,9.91 L1,4.39 L0,11 L-1,4.39 ' +
  'L-4.77,9.91 L-2.81,3.52 L-8.6,6.86 L-4.05,1.95 L-10.72,2.45 L-4.5,0 L-10.72,-2.45 ' +
  'L-4.05,-1.95 L-8.6,-6.86 L-2.81,-3.52 L-4.77,-9.91 L-1,-4.39 Z';

export function NakTahuMark({ size = 28, className, ...rest }: NakTahuMarkProps) {
  const decorative = rest['aria-hidden'];
  const [seasonal, setSeasonal] = useState(false);
  useEffect(() => {
    setSeasonal(inSeasonalWindow(new Date()));
  }, []);

  const sharedProps = {
    viewBox: '0 0 120 120',
    width: size,
    height: size,
    className,
    role: decorative ? undefined : ('img' as const),
    'aria-hidden': decorative,
    'aria-label': decorative ? undefined : 'NakTahu',
    xmlns: 'http://www.w3.org/2000/svg',
  };

  if (!seasonal) {
    return (
      <svg {...sharedProps}>
        <rect x="14" y="14" width="92" height="74" rx="30" fill="var(--brand-blue, #3B5BFF)" />
        <path d="M32 88 L32 108 L52 88 Z" fill="var(--brand-blue, #3B5BFF)" />
        <Hibiscus cx={98} cy={26} />
      </svg>
    );
  }

  return (
    <svg {...sharedProps}>
      <defs>
        <clipPath id="ntm-bubble-clip">
          <rect x="14" y="14" width="92" height="74" rx="30" />
        </clipPath>
      </defs>

      {/* tail — flat brand blue, unclipped, same shape as the default mark */}
      <path d="M32 88 L32 108 L52 88 Z" fill="var(--brand-blue, #3B5BFF)" />

      {/* Jalur Gemilang, clipped flush to the bubble's own silhouette. 7
          bands (not the real flag's 14 stripes, but more than this file's
          earlier 3-band pass) — a closer match to the reference at a scale
          this mark still reads at. */}
      <g clipPath="url(#ntm-bubble-clip)">
        <rect x="14" y="14" width="92" height="74" fill="#CC0001" />
        <rect x="14" y="24.57" width="92" height="10.57" fill="#ffffff" />
        <rect x="14" y="45.71" width="92" height="10.57" fill="#ffffff" />
        <rect x="14" y="66.86" width="92" height="10.57" fill="#ffffff" />
        {/* canton — enlarged to match the reference's proportions */}
        <rect x="14" y="14" width="44" height="32" fill="#010066" />
        {/* crescent — enlarged, opening left */}
        <circle cx="26" cy="30" r="10" fill="#FFCC00" />
        <circle cx="29.5" cy="28" r="8.5" fill="#010066" />
        {/* star — the real 14-point Bintang Persekutuan, enlarged */}
        <path d={STAR_14_POINT_PATH} fill="#FFCC00" transform="translate(45, 30)" />
      </g>

      <Hibiscus cx={98} cy={26} />
    </svg>
  );
}
