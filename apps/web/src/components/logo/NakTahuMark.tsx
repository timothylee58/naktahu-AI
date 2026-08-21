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
// federal territories, outer radius 8 / inner radius 3.3, centred at the
// origin. Generated once (28 alternating outer/inner vertices) and pasted
// as a literal so no trig runs at render time.
const STAR_14_POINT_PATH =
  'M0,-8 L0.73,-3.22 L3.47,-7.21 L2.06,-2.58 L6.25,-4.99 L2.97,-1.43 L7.8,-1.78 L3.3,0 ' +
  'L7.8,1.78 L2.97,1.43 L6.25,4.99 L2.06,2.58 L3.47,7.21 L0.73,3.22 L0,8 L-0.73,3.22 ' +
  'L-3.47,7.21 L-2.06,2.58 L-6.25,4.99 L-2.97,1.43 L-7.8,1.78 L-3.3,0 L-7.8,-1.78 ' +
  'L-2.97,-1.43 L-6.25,-4.99 L-2.06,-2.58 L-3.47,-7.21 L-0.73,-3.22 Z';

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

      {/* Jalur Gemilang, clipped flush to the bubble's own silhouette. */}
      <g clipPath="url(#ntm-bubble-clip)">
        <rect x="14" y="14" width="92" height="74" fill="#CC0001" />
        <rect x="14" y="28.8" width="92" height="14.8" fill="#ffffff" />
        <rect x="14" y="58.4" width="92" height="14.8" fill="#ffffff" />
        {/* canton */}
        <rect x="14" y="14" width="47" height="30" fill="#010066" />
        {/* crescent */}
        <circle cx="30" cy="27" r="8.5" fill="#FFCC00" />
        <circle cx="33.5" cy="24.5" r="7.2" fill="#010066" />
        {/* star — the real 14-point Bintang Persekutuan */}
        <path d={STAR_14_POINT_PATH} fill="#FFCC00" transform="translate(46, 28)" />
      </g>

      <Hibiscus cx={98} cy={26} />
    </svg>
  );
}
