import { cn } from '@/lib/utils';
import { FILL_CLASS, segmentCount, type CrowdStatus } from '@/lib/warung-watch/crowd';

interface StatusMeterProps {
  status: CrowdStatus;
  stale?: boolean;
  size?: 'sm' | 'lg';
  className?: string;
}

// Decorative: the level word always sits next to it, so colour is never the only cue.
export function StatusMeter({ status, stale = false, size = 'sm', className }: StatusMeterProps) {
  const filled = segmentCount(status);
  return (
    <span className={cn('inline-flex items-end gap-1', className)} aria-hidden>
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className={cn(
            'rounded-sm',
            size === 'lg' ? 'w-3' : 'w-2',
            size === 'lg' ? ['h-3', 'h-5', 'h-7'][index] : ['h-2', 'h-3.5', 'h-5'][index],
            index < filled ? (stale ? 'bg-nk-muted-aa/60' : FILL_CLASS[status]) : 'bg-[var(--nk-track)]',
          )}
        />
      ))}
    </span>
  );
}
