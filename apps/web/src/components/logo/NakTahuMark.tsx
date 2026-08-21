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
 * swaps to a "Merdeka Bubble" variant — a white-edged, wave-cut Jalur
 * Gemilang badge floating centred inside the bubble (blue bubble visibly
 * showing around it, not clipped edge-to-edge to the bubble outline),
 * plus the same hibiscus at the top-right corner. Matches the attached
 * reference: one path (FLAG_PATH) drawn twice — once stroked white as the
 * border, once as a clipPath for the striped/canton content — so the
 * border follows the wavy silhouette exactly instead of a separate offset
 * shape that could drift from it.
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

// Local coordinate frame (0,0 top-left), ~46 wide x 30 tall: straight,
// rounded left edge (the "pole" side) and a wavy right edge — two gentle
// S-bumps — reading as cloth flutter without needing runtime animation.
const FLAG_PATH =
  'M6,0 L36,0 Q44,0 42,6 Q40,12 46,15 Q40,18 42,24 Q44,30 36,30 L6,30 Q0,30 0,24 L0,6 Q0,0 6,0 Z';

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
        <clipPath id="ntm-flag-clip">
          <path d={FLAG_PATH} />
        </clipPath>
      </defs>

      <rect x="14" y="14" width="92" height="74" rx="30" fill="var(--brand-blue, #3B5BFF)" />
      <path d="M32 88 L32 108 L52 88 Z" fill="var(--brand-blue, #3B5BFF)" />

      {/* Flag badge — centred in the bubble with visible blue margin all
          round, not clipped flush to the bubble outline. Rotated slightly
          for a dynamic, "just fluttered" angle. */}
      <g transform="translate(37, 45) rotate(-8 23 15)">
        {/* white border — the same path, stroked, so it traces the wave
            exactly rather than a separately-drawn offset shape */}
        <path d={FLAG_PATH} fill="#ffffff" stroke="#ffffff" strokeWidth="4" strokeLinejoin="round" />
        <g clipPath="url(#ntm-flag-clip)">
          <rect x="0" y="0" width="46" height="30" fill="#CC0001" />
          <rect x="0" y="6.4" width="46" height="4.3" fill="#ffffff" />
          <rect x="0" y="15" width="46" height="4.3" fill="#ffffff" />
          <rect x="0" y="23.6" width="46" height="4.3" fill="#ffffff" />
          {/* canton */}
          <rect x="0" y="0" width="22" height="15" fill="#010066" />
          {/* crescent */}
          <circle cx="9" cy="7.5" r="4.6" fill="#FFCC00" />
          <circle cx="10.6" cy="6" r="3.9" fill="#010066" />
          {/* star */}
          <path
            d="M18.5 1.4 L19.6 4.6 L23 4.6 L20.2 6.6 L21.3 9.8 L18.5 7.8 L15.7 9.8 L16.8 6.6 L14 4.6 L17.4 4.6 Z"
            fill="#FFCC00"
          />
          {/* fold highlight along the wave */}
          <path d="M0,0 L36,0 L18,30 L0,30 Z" fill="#ffffff" opacity="0.12" />
        </g>
      </g>

      <Hibiscus cx={98} cy={26} />
    </svg>
  );
}
