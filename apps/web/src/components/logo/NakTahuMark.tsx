/**
 * "Hibiscus-Notch" — the NakTahu brand mark.
 *
 * A rounded speech bubble (the answer) with five amber dots in a loose
 * pentagon at the top-right — a nod to the bunga raya without reading as an
 * official government seal, which this product must never imply.
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

export function NakTahuMark({ size = 28, className, ...rest }: NakTahuMarkProps) {
  const decorative = rest['aria-hidden'];
  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      className={className}
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative}
      aria-label={decorative ? undefined : 'NakTahu'}
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect
        x="14"
        y="14"
        width="92"
        height="74"
        rx="30"
        fill="var(--brand-blue, #3B5BFF)"
      />
      <path d="M32 88 L32 108 L52 88 Z" fill="var(--brand-blue, #3B5BFF)" />
      <circle cx="96.0" cy="17.0" r="4" fill="var(--brand-amber, #FFB238)" />
      <circle cx="104.6" cy="23.2" r="4" fill="var(--brand-amber, #FFB238)" />
      <circle cx="101.3" cy="33.3" r="4" fill="var(--brand-amber, #FFB238)" />
      <circle cx="90.7" cy="33.3" r="4" fill="var(--brand-amber, #FFB238)" />
      <circle cx="87.4" cy="23.2" r="4" fill="var(--brand-amber, #FFB238)" />
    </svg>
  );
}
