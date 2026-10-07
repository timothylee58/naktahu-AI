/**
 * The "naktahu.my" wordmark, optionally preceded by the Hibiscus-Notch mark.
 *
 * Two deliberate choices:
 *
 * - "naktahu" inherits `currentColor` rather than hard-coding --brand-ink.
 *   The ink token (#14162B) is near-black, which is correct on the light
 *   theme and invisible on the dark one; every header that renders this
 *   already sets an appropriate text colour, so inheriting is what actually
 *   works in both themes. `.my` stays brand blue in both — it reads fine on
 *   either background.
 * - The name is one word to a screen reader ("naktahu.my"), so the mark beside
 *   it is aria-hidden and the two spans are not separately announced.
 */
import { NakTahuMark } from '@/components/logo/NakTahuMark';

interface NakTahuWordmarkProps {
  /** Render the Hibiscus-Notch mark before the text. */
  withMark?: boolean;
  /** Mark size in px; ignored when `withMark` is false. */
  markSize?: number;
  className?: string;
}

export function NakTahuWordmark({
  withMark = true,
  markSize = 26,
  className,
}: NakTahuWordmarkProps) {
  return (
    <span className={`inline-flex items-center gap-2 locale-nowrap ${className ?? ''}`}>
      {withMark && <NakTahuMark size={markSize} aria-hidden />}
      <span className="font-bold tracking-tight">
        naktahu
        <span style={{ color: 'var(--brand-blue, #3B5BFF)' }}>.my</span>
      </span>
    </span>
  );
}
