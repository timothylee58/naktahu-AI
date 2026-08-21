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
 * swaps to a "Merdeka Bubble" variant — the Jalur Gemilang CONFORMS to the
 * bubble's own silhouette (inset from it, not a smaller disconnected card
 * floating inside with a wide blue margin — an earlier attempt this file
 * held that read as generic) with a thin white inset border and a wavy
 * bottom hem for the flutter cue, plus the same hibiscus at the top-right
 * corner. Three concentric layers: the bubble itself (blue rim), a white
 * backing inset 4 units in, and the flag content inset 4 units further,
 * clipped to FLAG_CONTENT_PATH (rounded top corners, wavy bottom edge).
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

// Local coordinate frame (0,0 top-left), 76 wide x 58 tall: rounded top
// corners (matching the bubble's own rounding) and a wavy bottom edge —
// two gentle dips — so the flag content conforms to the bubble's shape
// instead of sitting in it as a plain disconnected rectangle.
const FLAG_CONTENT_PATH =
  'M20,0 L56,0 Q76,0 76,20 L76,44 C68,50 60,38 50,46 C40,54 30,38 20,46 C10,54 4,50 0,44 L0,20 Q0,0 20,0 Z';

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
        <clipPath id="ntm-flag-content-clip">
          <path d={FLAG_CONTENT_PATH} />
        </clipPath>
      </defs>

      {/* bubble — the thin blue rim visible around the white inset border */}
      <rect x="14" y="14" width="92" height="74" rx="30" fill="var(--brand-blue, #3B5BFF)" />
      <path d="M32 88 L32 108 L52 88 Z" fill="var(--brand-blue, #3B5BFF)" />

      {/* white backing — inset 4 units from the bubble, frames the flag */}
      <rect x="18" y="18" width="84" height="66" rx="26" fill="#ffffff" />

      {/* flag content — inset 4 units further, clipped to the wavy-bottom
          silhouette so it conforms to the bubble rather than floating as a
          disconnected card inside it */}
      <g transform="translate(22, 22)">
        <g clipPath="url(#ntm-flag-content-clip)">
          <rect x="0" y="0" width="76" height="58" fill="#CC0001" />
          <rect x="0" y="12.9" width="76" height="6.4" fill="#ffffff" />
          <rect x="0" y="25.8" width="76" height="6.4" fill="#ffffff" />
          <rect x="0" y="38.7" width="76" height="6.4" fill="#ffffff" />
          <rect x="0" y="51.6" width="76" height="6.4" fill="#ffffff" />
          {/* canton */}
          <rect x="0" y="0" width="38" height="26" fill="#010066" />
          {/* crescent */}
          <circle cx="15.5" cy="13" r="8" fill="#FFCC00" />
          <circle cx="18.3" cy="10.5" r="6.8" fill="#010066" />
          {/* star */}
          <path
            d="M31 3.5 L32.9 9 L38.7 9 L34 12.5 L35.8 18 L31 14.6 L26.2 18 L28 12.5 L23.3 9 L29.1 9 Z"
            fill="#FFCC00"
          />
          {/* fold highlight along the wave */}
          <path d="M0,0 L60,0 L30,58 L0,58 Z" fill="#ffffff" opacity="0.1" />
        </g>
      </g>

      <Hibiscus cx={98} cy={26} />
    </svg>
  );
}
