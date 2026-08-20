'use client';

/**
 * "Hibiscus-Notch" — the NakTahu brand mark.
 *
 * A rounded speech bubble (the answer) with five amber dots in a loose
 * pentagon at the top-right — a nod to the bunga raya without reading as an
 * official government seal, which this product must never imply.
 *
 * Aug25-Sep20 (Merdeka/Hari Malaysia window — lib/seasonal-window.ts):
 * swaps to a "Merdeka Bubble" variant — the same bubble silhouette filled
 * with a simplified Jalur Gemilang, five amber dots replaced with a
 * hibiscus-petal cluster in the same pentagon layout. Deliberately NOT the
 * full 14-stripe flag with precise star/crescent geometry: this mark
 * renders at 20-26px everywhere it's actually used (every call site is a
 * header logo, see NakTahuWordmark's consumers) — a faithful flag at that
 * size reads as a smear, not a flag. 5 thick stripes and an oversized
 * star/crescent stay legible at header scale instead.
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
        <circle cx="96.0" cy="17.0" r="4" fill="var(--brand-amber, #FFB238)" />
        <circle cx="104.6" cy="23.2" r="4" fill="var(--brand-amber, #FFB238)" />
        <circle cx="101.3" cy="33.3" r="4" fill="var(--brand-amber, #FFB238)" />
        <circle cx="90.7" cy="33.3" r="4" fill="var(--brand-amber, #FFB238)" />
        <circle cx="87.4" cy="23.2" r="4" fill="var(--brand-amber, #FFB238)" />
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

      {/* Simplified 5-band Jalur Gemilang, clipped to the bubble silhouette.
          Thick bands (not the real flag's 14 stripes) so the pattern still
          reads as "flag", not noise, at 20-26px. */}
      <g clipPath="url(#ntm-bubble-clip)">
        <rect x="14" y="14" width="92" height="74" fill="#CC0001" />
        <rect x="14" y="28.8" width="92" height="14.8" fill="#ffffff" />
        <rect x="14" y="58.4" width="92" height="14.8" fill="#ffffff" />
        {/* canton */}
        <rect x="14" y="14" width="47" height="30" fill="#010066" />
        {/* crescent */}
        <circle cx="30" cy="27" r="8.5" fill="#FFCC00" />
        <circle cx="33.5" cy="24.5" r="7.2" fill="#010066" />
        {/* star — 5-point, scaled/positioned over the canton */}
        <path
          d="M46 15.5 L48.1 21.7 L54.7 21.7 L49.4 25.6 L51.4 31.8 L46 27.9 L40.6 31.8 L42.6 25.6 L37.3 21.7 L43.9 21.7 Z"
          fill="#FFCC00"
        />
      </g>

      {/* hibiscus-petal cluster — same 5-position pentagon layout as the
          default mark's amber dots, now shaped as petals with a stamen
          centre, in the flag's own red rather than a new colour. */}
      <g fill="#CC0001">
        <ellipse cx="96.0" cy="17.0" rx="6.4" ry="3.6" transform="rotate(-54 96 17)" />
        <ellipse cx="104.6" cy="23.2" rx="6.4" ry="3.6" transform="rotate(18 104.6 23.2)" />
        <ellipse cx="101.3" cy="33.3" rx="6.4" ry="3.6" transform="rotate(90 101.3 33.3)" />
        <ellipse cx="90.7" cy="33.3" rx="6.4" ry="3.6" transform="rotate(162 90.7 33.3)" />
        <ellipse cx="87.4" cy="23.2" rx="6.4" ry="3.6" transform="rotate(234 87.4 23.2)" />
      </g>
      <circle cx="94" cy="25.6" r="3.2" fill="#FFCC00" />
    </svg>
  );
}
