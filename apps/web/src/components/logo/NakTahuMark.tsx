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
 * swaps to a "Merdeka Bubble" variant — the same bubble and hibiscus, plus
 * a contained Jalur Gemilang badge (its own white-bordered rounded shape,
 * not clipped to the bubble outline) centred inside, per the reference art.
 * A self-contained flag badge — not a flag clipped edge-to-edge across the
 * whole bubble, this file's earlier approach — reads clearer at the
 * 20-26px this mark actually renders at (every NakTahuWordmark call site
 * is a header logo): a white border separates "flag" from "bubble" the way
 * clipping the two together didn't.
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
      <rect x="14" y="14" width="92" height="74" rx="30" fill="var(--brand-blue, #3B5BFF)" />
      <path d="M32 88 L32 108 L52 88 Z" fill="var(--brand-blue, #3B5BFF)" />

      {/* Contained flag badge — its own rounded, white-bordered shape
          centred in the bubble, not clipped flush to the bubble outline.
          Slight rotation + a translucent diagonal fold highlight stand in
          for "waving cloth" at a scale too small for a real wave path. */}
      <g transform="rotate(-6 51 51)">
        <rect x="24" y="36" width="54" height="34" rx="7" fill="#ffffff" />
        <g clipPath="url(#ntm-flag-clip)">
          <rect x="26" y="38" width="50" height="30" fill="#CC0001" />
          <rect x="26" y="44.3" width="50" height="6" fill="#ffffff" />
          <rect x="26" y="56.9" width="50" height="6" fill="#ffffff" />
          <rect x="26" y="38" width="24" height="15" fill="#010066" />
          <circle cx="35" cy="45.5" r="4.6" fill="#FFCC00" />
          <circle cx="37" cy="44" r="3.9" fill="#010066" />
          <path
            d="M44.5 39.2 L45.4 41.7 L48 41.7 L45.9 43.2 L46.7 45.7 L44.5 44.2 L42.3 45.7 L43.1 43.2 L41 41.7 L43.6 41.7 Z"
            fill="#FFCC00"
          />
          {/* fold highlight — the "wave" cue */}
          <path d="M26 38 L76 38 L60 68 L26 68 Z" fill="#ffffff" opacity="0.14" />
        </g>
        <defs>
          <clipPath id="ntm-flag-clip">
            <rect x="26" y="38" width="50" height="30" rx="5.5" />
          </clipPath>
        </defs>
      </g>

      <Hibiscus cx={98} cy={26} />
    </svg>
  );
}
