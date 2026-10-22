import { ChevronRight, CircleDashed } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fill, freshnessTone, levelKey, TEXT_CLASS, type Place } from '@/lib/warung-watch/crowd';
import { StatusMeter } from './StatusMeter';

interface PlaceCardProps {
  place: Place;
  t: (key: string) => string;
  formatAgo: (iso: string | null) => string;
  onOpen: (place: Place) => void;
}

export function PlaceCard({ place, t, formatAgo, onOpen }: PlaceCardProps) {
  const { crowd } = place;
  const tone = freshnessTone(crowd);
  const where = [place.location, place.distance_m !== null ? fill(t('warung_watch.distance_m'), { n: place.distance_m }) : null]
    .filter(Boolean)
    .join(' · ');
  const when =
    tone === 'none'
      ? t('warung_watch.no_reports')
      : tone === 'fresh'
        ? `${fill(t('warung_watch.updated'), { time: formatAgo(crowd.last_updated) })} · ${fill(t('warung_watch.reports_n'), { n: crowd.report_count })}`
        : fill(t('warung_watch.stale_age'), { time: formatAgo(crowd.last_updated) });

  return (
    <button
      type="button"
      onClick={() => onOpen(place)}
      className="flex w-full min-h-[4.5rem] items-center gap-3 rounded-2xl border border-[var(--nk-border)] bg-nk-card p-3.5 text-left transition-colors hover:border-nk-official/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official"
    >
      <span className="flex w-16 shrink-0 flex-col items-center gap-1.5" aria-hidden={crowd.status ? undefined : true}>
        {crowd.status ? (
          <>
            <StatusMeter status={crowd.status} stale={tone === 'stale'} />
            <span className={cn('text-xs font-bold', tone === 'stale' ? 'text-nk-muted-aa' : TEXT_CLASS[crowd.status])}>
              {t(levelKey(crowd.status))}
            </span>
          </>
        ) : (
          <CircleDashed className="h-6 w-6 text-nk-muted-aa" />
        )}
      </span>
      <span className={cn('flex min-w-0 flex-1 flex-col gap-0.5', tone === 'stale' && 'opacity-80')}>
        <span className="truncate font-semibold text-nk-ink">{place.name}</span>
        {where && <span className="truncate text-sm text-nk-muted-aa">{where}</span>}
        <span className={cn('text-xs', tone === 'stale' ? 'text-nk-moderate-text' : 'text-nk-muted-aa')}>{when}</span>
      </span>
      <ChevronRight className="h-5 w-5 shrink-0 text-nk-muted-aa" aria-hidden />
    </button>
  );
}
