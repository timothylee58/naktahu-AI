export type CrowdStatus = 'empty' | 'moderate' | 'packed';

export const STATUSES: readonly CrowdStatus[] = ['empty', 'moderate', 'packed'];

export interface Counts {
  empty: number;
  moderate: number;
  packed: number;
}

export interface Crowd {
  status: CrowdStatus | null;
  is_fresh: boolean;
  report_count: number;
  last_updated: string | null;
  counts: Counts;
  hour_reports: number;
  hour_status: CrowdStatus | null;
}

export interface Place {
  key: string;
  name: string;
  location: string | null;
  verified: boolean;
  lat: number | null;
  lng: number | null;
  distance_m: number | null;
  crowd: Crowd;
}

export interface Coords {
  lat: number;
  lng: number;
}

export const EMPTY_CROWD: Crowd = {
  status: null,
  is_fresh: false,
  report_count: 0,
  last_updated: null,
  counts: { empty: 0, moderate: 0, packed: 0 },
  hour_reports: 0,
  hour_status: null,
};

export function fill(template: string, values: Record<string, string | number>): string {
  return Object.entries(values).reduce((text, [key, value]) => text.split(`{${key}}`).join(String(value)), template);
}

export function normName(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, ' ');
}

export function isStatus(value: unknown): value is CrowdStatus {
  return value === 'empty' || value === 'moderate' || value === 'packed';
}

export function asCrowd(data: Record<string, unknown> | null): Crowd {
  if (!data) return EMPTY_CROWD;
  const counts = (data.counts ?? {}) as Partial<Counts>;
  return {
    status: isStatus(data.status) ? data.status : null,
    is_fresh: data.is_fresh === true,
    report_count: typeof data.report_count === 'number' ? data.report_count : 0,
    last_updated: typeof data.last_updated === 'string' ? data.last_updated : null,
    counts: {
      empty: typeof counts.empty === 'number' ? counts.empty : 0,
      moderate: typeof counts.moderate === 'number' ? counts.moderate : 0,
      packed: typeof counts.packed === 'number' ? counts.packed : 0,
    },
    hour_reports: typeof data.hour_reports === 'number' ? data.hour_reports : 0,
    hour_status: isStatus(data.hour_status) ? data.hour_status : null,
  };
}

export function levelKey(status: CrowdStatus): string {
  return `warung_watch.level.${status}`;
}

export function hintKey(status: CrowdStatus): string {
  return `warung_watch.hint.${status}`;
}

export function segmentCount(status: CrowdStatus): number {
  return STATUSES.indexOf(status) + 1;
}

// Spelled out (not built from the status name) so Tailwind sees every class.
export const FILL_CLASS: Record<CrowdStatus, string> = {
  empty: 'bg-nk-quiet',
  moderate: 'bg-nk-moderate',
  packed: 'bg-nk-packed',
};

export const TEXT_CLASS: Record<CrowdStatus, string> = {
  empty: 'text-nk-quiet-text',
  moderate: 'text-nk-moderate-text',
  packed: 'text-nk-packed-text',
};

export function directionsUrl(place: Pick<Place, 'name' | 'lat' | 'lng'>): string {
  if (place.lat !== null && place.lng !== null) {
    return `https://www.google.com/maps/search/?api=1&query=${place.lat},${place.lng}`;
  }
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name)}`;
}

export function haversineM(a: Coords, b: Coords): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return Math.round(2 * 6_371_000 * Math.asin(Math.sqrt(h)));
}

// Arrow-key movement through a listbox. -1 means "nothing active yet", so the
// first ArrowDown lands on 0 and ArrowUp from nothing lands on the last row.
export function stepIndex(current: number, delta: 1 | -1, length: number): number {
  if (length <= 0) return -1;
  if (current < 0) return delta === 1 ? 0 : length - 1;
  return (current + delta + length) % length;
}

export type FreshnessTone = 'none' | 'fresh' | 'stale';

export function freshnessTone(crowd: Crowd): FreshnessTone {
  if (!crowd.status) return 'none';
  return crowd.is_fresh ? 'fresh' : 'stale';
}
