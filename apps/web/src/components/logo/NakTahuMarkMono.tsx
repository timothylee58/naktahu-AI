/**
 * Single-colour silhouette of the NakTahu mark — bubble only, amber dots
 * dropped.
 *
 * `fill="currentColor"` on purpose: at favicon sizes the five 4px dots turn to
 * mud, and this variant also has to sit in inherited-colour contexts (dark
 * headers, print, a disabled state) where a fixed brand blue would clash.
 * Drop it anywhere and it takes the surrounding text colour.
 */
interface NakTahuMarkMonoProps {
  /** Rendered width and height in px. */
  size?: number;
  className?: string;
  /** Set when the mark sits next to a visible wordmark, so screen readers
   *  do not hear the brand name twice. */
  'aria-hidden'?: boolean;
}

export function NakTahuMarkMono({ size = 28, className, ...rest }: NakTahuMarkMonoProps) {
  const decorative = rest['aria-hidden'];
  return (
    <svg
      viewBox="0 0 120 120"
      width={size}
      height={size}
      fill="currentColor"
      className={className}
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative}
      aria-label={decorative ? undefined : 'NakTahu'}
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="14" y="14" width="92" height="74" rx="30" />
      <path d="M32 88 L32 108 L52 88 Z" />
    </svg>
  );
}
