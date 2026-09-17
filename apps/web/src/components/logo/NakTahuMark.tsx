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
 * Inlined as JSX rather than imported from a .svg file: this repo has no
 * @svgr/webpack (or equivalent) configured in next.config.ts, and every other
 * icon here is inline SVG too.
 *
 * Colours resolve from the brand tokens in globals.css, with literal
 * fallbacks so the mark still renders correctly anywhere the cascade does not
 * reach (e.g. an SVG rasterised out of context).
 */
interface NakTahuMarkProps {
  /** Rendered width and height in px. */
  size?: number;
  className?: string;
  /** Set when the mark sits next to a visible wordmark, so screen readers
   *  do not hear the brand name twice. */
  'aria-hidden'?: boolean;
}

/** Single bunga raya — 5 overlapping petals + stamen, centred on `cx,cy`. */
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

  return (
    <svg {...sharedProps}>
      <rect x="14" y="14" width="92" height="74" rx="30" fill="var(--brand-blue, #3B5BFF)" />
      <path d="M32 88 L32 108 L52 88 Z" fill="var(--brand-blue, #3B5BFF)" />
      <Hibiscus cx={98} cy={26} />
    </svg>
  );
}
