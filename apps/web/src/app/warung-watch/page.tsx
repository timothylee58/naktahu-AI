'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { NakTahuWordmark } from '@/components/logo/NakTahuWordmark';
import { API_BASE } from '@/lib/api-base';
import { WarungPriceChart, type PriceHistoryPoint } from '@/components/warung-watch/WarungPriceChart';

const ANON_SESSION_KEY = 'naktahu_anon_session_id';
const RADIUS_M = 800;

type CrowdStatus = 'empty' | 'moderate' | 'packed';
type Screen = 'home' | 'detail' | 'thanks';

interface Counts {
  empty: number;
  moderate: number;
  packed: number;
}

interface Crowd {
  status: CrowdStatus | null;
  is_fresh: boolean;
  report_count: number;
  last_updated: string | null;
  counts: Counts;
  hour_reports: number;
  hour_status: CrowdStatus | null;
}

interface Place {
  key: string;
  name: string;
  location: string | null;
  verified: boolean;
  lat: number | null;
  lng: number | null;
  distance_m: number | null;
  crowd: Crowd;
}

interface Coords {
  lat: number;
  lng: number;
}

const EMPTY_CROWD: Crowd = {
  status: null,
  is_fresh: false,
  report_count: 0,
  last_updated: null,
  counts: { empty: 0, moderate: 0, packed: 0 },
  hour_reports: 0,
  hour_status: null,
};

function fill(template: string, values: Record<string, string | number>): string {
  return Object.entries(values).reduce((text, [key, value]) => text.split(`{${key}}`).join(String(value)), template);
}

function normName(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, ' ');
}

function isStatus(value: unknown): value is CrowdStatus {
  return value === 'empty' || value === 'moderate' || value === 'packed';
}

function asCrowd(data: Record<string, unknown> | null): Crowd {
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

function levelKey(status: CrowdStatus): string {
  switch (status) {
    case 'empty':
      return 'warung_watch.level.empty';
    case 'moderate':
      return 'warung_watch.level.moderate';
    case 'packed':
      return 'warung_watch.level.packed';
    default: {
      const neverStatus: never = status;
      return neverStatus;
    }
  }
}

function hintKey(status: CrowdStatus): string {
  switch (status) {
    case 'empty':
      return 'warung_watch.hint.empty';
    case 'moderate':
      return 'warung_watch.hint.moderate';
    case 'packed':
      return 'warung_watch.hint.packed';
    default: {
      const neverStatus: never = status;
      return neverStatus;
    }
  }
}

function segmentCount(status: CrowdStatus): number {
  switch (status) {
    case 'empty':
      return 1;
    case 'moderate':
      return 2;
    case 'packed':
      return 3;
    default: {
      const neverStatus: never = status;
      return neverStatus;
    }
  }
}

function segmentClass(status: CrowdStatus, stale: boolean): string {
  if (stale) return 'bg-zinc-400';
  switch (status) {
    case 'empty':
      return 'bg-emerald-500';
    case 'moderate':
      return 'bg-amber-500';
    case 'packed':
      return 'bg-red-500';
    default: {
      const neverStatus: never = status;
      return neverStatus;
    }
  }
}

function directionsUrl(place: Place): string {
  if (place.lat !== null && place.lng !== null) {
    return `https://www.google.com/maps/search/?api=1&query=${place.lat},${place.lng}`;
  }
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name)}`;
}

async function apiFetch(path: string, accessToken: string | null, init?: RequestInit) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  return fetch(`${API_BASE}${path}`, { ...init, headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) } });
}

function StatusMeter({ status, stale }: { status: CrowdStatus; stale: boolean }) {
  const filled = segmentCount(status);
  const tone = segmentClass(status, stale);
  return (
    <span className="inline-flex items-center gap-0.5" aria-hidden>
      {[0, 1, 2].map((index) => (
        <span key={index} className={`h-2 w-3 rounded-sm ${index < filled ? tone : 'bg-zinc-200 dark:bg-white/15'}`} />
      ))}
    </span>
  );
}

export default function WarungWatchPage() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const { user, accessToken } = useSupabaseSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const [screen, setScreen] = useState<Screen>('home');
  const [browsing, setBrowsing] = useState<'ask' | 'list' | 'search'>('ask');
  const [locating, setLocating] = useState(false);
  const [coords, setCoords] = useState<Coords | null>(null);
  const [places, setPlaces] = useState<Place[]>([]);
  const [listError, setListError] = useState(false);
  const [quietOnly, setQuietOnly] = useState(false);
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<Place[]>([]);
  const [pickForReport, setPickForReport] = useState(false);

  const [selected, setSelected] = useState<Place | null>(null);
  const [detailError, setDetailError] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [priceHistory, setPriceHistory] = useState<PriceHistoryPoint[]>([]);

  const [sheet, setSheet] = useState(false);
  const [reportStatus, setReportStatus] = useState<CrowdStatus | null>(null);
  const [priceItem, setPriceItem] = useState('');
  const [priceMyr, setPriceMyr] = useState('');
  const [priceError, setPriceError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [reportError, setReportError] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(ANON_SESSION_KEY)) {
      localStorage.setItem(ANON_SESSION_KEY, crypto.randomUUID());
    }
  }, []);

  useEffect(() => {
    if (!navigator.permissions?.query) return;
    navigator.permissions
      .query({ name: 'geolocation' })
      .then((result) => {
        if (result.state === 'granted') loadNearby();
      })
      .catch(() => {
        /* Permission query can throw when the page policy blocks geolocation. */
      });
    // loadNearby is stable enough for the granted-on-arrival case.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const formatAgo = (iso: string | null): string => {
    if (!iso) return t('warung_watch.time.just_now');
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return t('warung_watch.time.just_now');
    const minutes = Math.max(0, Math.round((Date.now() - then) / 60000));
    if (minutes < 1) return t('warung_watch.time.just_now');
    if (minutes < 60) return fill(t('warung_watch.time.minutes'), { n: minutes });
    const hours = Math.floor(minutes / 60);
    return fill(t('warung_watch.time.hours'), { h: hours, m: minutes % 60 });
  };

  const loadNearby = () => {
    if (!('geolocation' in navigator)) {
      setBrowsing('ask');
      return;
    }
    setLocating(true);
    setListError(false);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const next = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setCoords(next);
        setBrowsing('list');
        void fetchNearby(next).finally(() => setLocating(false));
      },
      () => {
        setLocating(false);
        setBrowsing('ask');
      },
      { timeout: 10000, maximumAge: 60000 },
    );
  };

  const fetchNearby = async (next: Coords) => {
    try {
      const [reportsRes, placesRes] = await Promise.all([
        apiFetch(`/api/v1/warung-watch/nearby-reports?lat=${next.lat}&lng=${next.lng}&radius_m=${RADIUS_M}`, accessToken),
        apiFetch(`/api/v1/warung-watch/nearby?lat=${next.lat}&lng=${next.lng}&radius_m=${RADIUS_M}`, accessToken),
      ]);
      if (!reportsRes.ok && !placesRes.ok) {
        setListError(true);
        return;
      }
      const reports = reportsRes.ok
        ? ((await reportsRes.json()) as { warungs: Array<Record<string, unknown> & { warung: Record<string, unknown> }> })
        : { warungs: [] };
      const google = placesRes.ok
        ? ((await placesRes.json()) as { places: Array<{ place_id: string | null; name: string; address: string | null; lat: number | null; lng: number | null }> })
        : { places: [] };

      const fromReports: Place[] = (reports.warungs ?? []).map((row) => {
        const warung = row.warung ?? {};
        const name = String(warung.name ?? '');
        return {
          key: String(warung.id ?? name),
          name,
          location: typeof warung.location === 'string' ? warung.location : null,
          verified: warung.verified === true,
          lat: typeof warung.lat === 'number' ? warung.lat : null,
          lng: typeof warung.lng === 'number' ? warung.lng : null,
          distance_m: typeof warung.distance_m === 'number' ? warung.distance_m : null,
          crowd: asCrowd(row),
        };
      });
      const known = new Set(fromReports.map((place) => normName(place.name)));
      const extras: Place[] = [];
      for (const place of google.places ?? []) {
        if (known.has(normName(place.name))) continue;
        let distance: number | null = null;
        if (place.lat !== null && place.lng !== null) {
          const toRad = (deg: number) => (deg * Math.PI) / 180;
          const dLat = toRad(place.lat - next.lat);
          const dLng = toRad(place.lng - next.lng);
          const a =
            Math.sin(dLat / 2) ** 2 +
            Math.cos(toRad(next.lat)) * Math.cos(toRad(place.lat)) * Math.sin(dLng / 2) ** 2;
          distance = Math.round(2 * 6_371_000 * Math.asin(Math.sqrt(a)));
          if (distance > RADIUS_M) continue;
        }
        extras.push({
          key: place.place_id ?? place.name,
          name: place.name,
          location: place.address,
          verified: false,
          lat: place.lat,
          lng: place.lng,
          distance_m: distance,
          crowd: EMPTY_CROWD,
        });
      }
      setPlaces([...fromReports, ...extras]);
      setListError(!reportsRes.ok);
    } catch {
      setListError(true);
    }
  };

  useEffect(() => {
    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    let active = true;
    const timeout = setTimeout(() => {
      apiFetch(`/api/v1/warung-watch/search?q=${encodeURIComponent(query.trim())}`, accessToken)
        .then((res) => (res.ok ? res.json() : []))
        .then((data: Array<{ id: string; name: string; location: string | null; verified: boolean; lat?: number | null; lng?: number | null }>) => {
          if (!active) return;
          setSuggestions(
            data.map((row) => ({
              key: row.id,
              name: row.name,
              location: row.location,
              verified: row.verified,
              lat: row.lat ?? null,
              lng: row.lng ?? null,
              distance_m: null,
              crowd: EMPTY_CROWD,
            })),
          );
        })
        .catch(() => {
          if (active) setSuggestions([]);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timeout);
    };
  }, [query, accessToken]);

  const openPlace = async (place: Place, options?: { report?: boolean; stay?: boolean }) => {
    setSelected(place);
    if (!options?.stay) {
      setScreen('detail');
      setSheet(Boolean(options?.report));
    }
    setDetailError(false);
    setDetailLoading(true);
    setPriceHistory([]);
    setReportError(false);
    setReportStatus(null);
    setPriceItem('');
    setPriceMyr('');
    setPriceError(false);
    try {
      const res = await apiFetch(`/api/v1/warung-watch/status?name=${encodeURIComponent(place.name)}`, accessToken);
      if (!res.ok) throw new Error('fetch-failed');
      const data = (await res.json()) as Record<string, unknown> & { warung?: Record<string, unknown> | null };
      const warung = data.warung ?? null;
      setSelected({
        ...place,
        key: typeof warung?.id === 'string' ? warung.id : place.key,
        location: typeof warung?.location === 'string' ? warung.location : place.location,
        verified: warung?.verified === true || place.verified,
        lat: typeof warung?.lat === 'number' ? warung.lat : place.lat,
        lng: typeof warung?.lng === 'number' ? warung.lng : place.lng,
        crowd: asCrowd(data),
      });
      const priceRes = await apiFetch(`/api/v1/warung-watch/price-history?name=${encodeURIComponent(place.name)}`, accessToken);
      if (priceRes.ok) {
        const priced = (await priceRes.json()) as { history: PriceHistoryPoint[] };
        setPriceHistory(priced.history ?? []);
      }
    } catch {
      setDetailError(true);
    } finally {
      setDetailLoading(false);
    }
  };

  const submitReport = async () => {
    if (!selected || !reportStatus) return;
    const item = priceItem.trim();
    const amount = priceMyr.trim();
    if ((item === '') !== (amount === '')) {
      setPriceError(true);
      return;
    }
    const parsed = amount === '' ? null : Number(amount);
    if (parsed !== null && Number.isNaN(parsed)) {
      setPriceError(true);
      return;
    }
    setPriceError(false);
    setSubmitting(true);
    setReportError(false);
    try {
      const res = await apiFetch('/api/v1/warung-watch/checkin', accessToken, {
        method: 'POST',
        body: JSON.stringify({
          name: selected.name,
          status: reportStatus,
          location: selected.location,
          lat: coords?.lat ?? selected.lat,
          lng: coords?.lng ?? selected.lng,
          anon_session_id: localStorage.getItem(ANON_SESSION_KEY),
          ...(item && parsed !== null ? { price_item: item, price_myr: parsed } : {}),
        }),
      });
      if (!res.ok) throw new Error('submit-failed');
      setSheet(false);
      setScreen('thanks');
      await openPlace(
        { ...selected, crowd: { ...selected.crowd, status: reportStatus, is_fresh: true, last_updated: new Date().toISOString() } },
        { stay: true },
      );
    } catch {
      setReportError(true);
    } finally {
      setSubmitting(false);
    }
  };

  const shareStatus = async () => {
    if (!selected?.crowd.status) return;
    const statusLabel = t(levelKey(selected.crowd.status));
    const text = fill(t('warung_watch.share_text'), { name: selected.name, status: statusLabel });
    if (navigator.share) {
      try {
        await navigator.share({ title: selected.name, text, url: window.location.href });
        return;
      } catch {
        return;
      }
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(`${text} ${window.location.href}`)}`, '_blank', 'noopener,noreferrer');
  };

  const visiblePlaces = useMemo(() => {
    if (!quietOnly) return places;
    return places.filter((place) => place.crowd.status === 'empty' && place.crowd.is_fresh);
  }, [places, quietOnly]);

  const exactSuggestion = suggestions.some((place) => normName(place.name) === normName(query));
  const latestPrice = priceHistory.length > 0 ? priceHistory[priceHistory.length - 1] : null;

  const card = isDark ? 'bg-white/5 border-white/10' : 'bg-white border-zinc-200';
  const muted = isDark ? 'text-zinc-400' : 'text-zinc-500';

  return (
    <div className={`flex h-full ${isDark ? 'bg-[#12151C] text-white' : 'bg-zinc-50/50 text-zinc-900'}`}>
      <AppSidebar
        variant={isDark ? 'dark' : 'light'}
        isMobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        user={user}
        accessToken={accessToken}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((current) => !current)}
      />
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-y-auto">
        <header
          className={`flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b backdrop-blur-md sticky top-0 z-10 ${
            isDark ? 'border-white/10 bg-[#12151C]/90 text-white' : 'border-zinc-100 bg-white/90 text-zinc-900'
          }`}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label={t('header.menu')}
            className={`p-1.5 rounded-lg transition-colors lg:hidden ${isDark ? 'text-zinc-400 hover:bg-white/10' : 'text-zinc-500 hover:bg-zinc-100'}`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
              <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
            </svg>
          </button>
          <Link href="/" className="flex flex-col">
            <NakTahuWordmark markSize={20} className="text-base" />
            <span className={`text-xs ${muted}`}>{t('header.subtitle')}</span>
          </Link>
        </header>

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="max-w-md mx-auto px-4 py-6 w-full flex flex-col gap-4">
          {screen === 'home' && (
            <>
              <div>
                <h1 className="font-display text-2xl font-bold">{t('warung_watch.title')}</h1>
                <p className={`text-sm mt-1 ${muted}`}>{t('warung_watch.lede')}</p>
                <span className={`inline-block mt-2 text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${isDark ? 'border-white/15 text-zinc-300' : 'border-zinc-200 text-zinc-600'}`}>
                  {t('warung_watch.badge.community')}
                </span>
              </div>

              {browsing === 'list' && coords && (
                <div className="flex items-center justify-between text-sm">
                  <p>{fill(t('warung_watch.within'), { m: RADIUS_M })}</p>
                  <button type="button" onClick={() => setBrowsing('search')} className="font-semibold text-nk-official">
                    {t('warung_watch.change')}
                  </button>
                </div>
              )}

              {(browsing === 'ask' || browsing === 'search') && (
                <section className={`rounded-2xl border p-4 flex flex-col gap-3 ${card}`}>
                  {browsing === 'ask' && (
                    <>
                      <h2 className="font-semibold">{t('warung_watch.location_off_title')}</h2>
                      <p className={`text-sm ${muted}`}>{t('warung_watch.location_off_body')}</p>
                      <button
                        type="button"
                        onClick={loadNearby}
                        disabled={locating}
                        className="px-4 py-2.5 rounded-xl bg-nk-official text-white text-sm font-semibold disabled:opacity-50"
                      >
                        {locating ? t('warung_watch.nearby_locating') : t('warung_watch.use_location')}
                      </button>
                    </>
                  )}
                  <label className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>{t('warung_watch.search_label')}</label>
                  <input
                    ref={searchRef}
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={t('warung_watch.search_placeholder')}
                    className={`w-full border rounded-xl p-3 text-sm bg-transparent focus:outline-none focus:border-nk-official ${isDark ? 'border-white/10' : 'border-zinc-200'}`}
                  />
                  {pickForReport && <p className={`text-xs ${muted}`}>{t('warung_watch.pick_place')}</p>}
                  {suggestions.length > 0 && (
                    <ul className="flex flex-col gap-1">
                      {suggestions.map((place) => (
                        <li key={place.key}>
                          <button type="button" onClick={() => void openPlace(place, { report: pickForReport })} className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-zinc-100 dark:hover:bg-white/5">
                            {place.name}
                            {place.location && <span className={`block text-xs ${muted}`}>{place.location}</span>}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  {query.trim().length >= 2 && !exactSuggestion && (
                    <button
                      type="button"
                      onClick={() =>
                        void openPlace(
                          { key: `new:${normName(query)}`, name: query.trim(), location: null, verified: false, lat: null, lng: null, distance_m: null, crowd: EMPTY_CROWD },
                          { report: pickForReport },
                        )
                      }
                      className="text-left text-sm font-semibold text-nk-official"
                    >
                      {fill(t('warung_watch.add_place'), { name: query.trim() })}
                    </button>
                  )}
                </section>
              )}

              {browsing === 'list' && (
                <section className={`rounded-2xl border p-4 flex items-center justify-between gap-3 ${card}`}>
                  <div>
                    <h2 className="font-semibold text-sm">{t('warung_watch.here_title')}</h2>
                    <p className={`text-xs mt-1 ${muted}`}>{t('warung_watch.here_body')}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setPickForReport(true);
                      setBrowsing('search');
                      setTimeout(() => searchRef.current?.focus(), 0);
                    }}
                    className="px-3 py-2 rounded-xl bg-nk-official text-white text-sm font-semibold"
                  >
                    {t('warung_watch.report')}
                  </button>
                </section>
              )}

              {locating && (
                <div className="flex flex-col gap-2" aria-hidden>
                  {[0, 1, 2].map((row) => (
                    <div key={row} className={`h-16 rounded-2xl animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-200'}`} />
                  ))}
                </div>
              )}

              {listError && (
                <section className={`rounded-2xl border p-4 flex flex-col gap-2 ${card}`}>
                  <h2 className="font-semibold">{t('warung_watch.load_title')}</h2>
                  <p className={`text-sm ${muted}`}>{t('warung_watch.load_body')}</p>
                  <button type="button" onClick={loadNearby} className="self-start px-4 py-2 rounded-xl bg-nk-official text-white text-sm font-semibold">
                    {t('warung_watch.try_again')}
                  </button>
                </section>
              )}

              {browsing === 'list' && !locating && places.length > 0 && (
                <div className="flex justify-end">
                  <button type="button" onClick={() => setQuietOnly((current) => !current)} className={`text-xs font-semibold px-2 py-1 rounded-full border ${quietOnly ? 'bg-emerald-600 text-white border-emerald-600' : isDark ? 'border-white/15' : 'border-zinc-200'}`}>
                    {t('warung_watch.quiet_only')}
                  </button>
                </div>
              )}

              {browsing === 'list' && !locating && quietOnly && places.length > 0 && visiblePlaces.length === 0 && (
                <section className={`rounded-2xl border p-4 flex flex-col gap-2 ${card}`}>
                  <h2 className="font-semibold">{t('warung_watch.nothing_quiet_title')}</h2>
                  <p className={`text-sm ${muted}`}>{t('warung_watch.nothing_quiet_body')}</p>
                  <button type="button" onClick={() => setQuietOnly(false)} className="self-start px-4 py-2 rounded-xl bg-nk-official text-white text-sm font-semibold">
                    {t('warung_watch.show_all')}
                  </button>
                </section>
              )}

              {browsing === 'list' && !locating && places.length === 0 && !listError && (
                <section className={`rounded-2xl border p-4 ${card}`}>
                  <h2 className="font-semibold">{t('warung_watch.none_nearby_title')}</h2>
                  <p className={`text-sm mt-1 ${muted}`}>{t('warung_watch.none_nearby_body')}</p>
                </section>
              )}

              {browsing === 'list' && !locating && (
                <ul className="flex flex-col gap-2">
                  {visiblePlaces.map((place) => (
                    <li key={place.key}>
                      <button type="button" onClick={() => void openPlace(place)} className={`w-full text-left rounded-2xl border p-4 ${card}`}>
                        <span className="flex items-center justify-between gap-3">
                          <span className="font-semibold">{place.name}</span>
                          {place.crowd.status && (
                            <span className="inline-flex items-center gap-2 text-sm">
                              <StatusMeter status={place.crowd.status} stale={!place.crowd.is_fresh} />
                              {t(levelKey(place.crowd.status))}
                            </span>
                          )}
                        </span>
                        <span className={`block text-xs mt-1 ${!place.crowd.is_fresh && place.crowd.status ? 'text-amber-600 dark:text-amber-400' : muted}`}>
                          {(() => {
                            const where = [place.location, place.distance_m !== null ? fill(t('warung_watch.distance_m'), { n: place.distance_m }) : null]
                              .filter(Boolean)
                              .join(' · ');
                            const when = !place.crowd.status
                              ? t('warung_watch.no_reports')
                              : place.crowd.is_fresh
                                ? `${fill(t('warung_watch.updated'), { time: formatAgo(place.crowd.last_updated) })} · ${fill(t('warung_watch.reports_n'), { n: place.crowd.report_count })}`
                                : fill(t('warung_watch.stale_age'), { time: formatAgo(place.crowd.last_updated) });
                            return [where, when].filter(Boolean).join(' · ');
                          })()}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}

          {screen !== 'home' && selected && (
            <div className="flex flex-col gap-4">
              <button type="button" onClick={() => { setScreen('home'); setSheet(false); setPickForReport(false); }} className={`self-start text-sm font-semibold ${muted}`}>
                ← {t('warung_watch.back')}
              </button>

              {screen === 'thanks' && selected.crowd.status && (
                <section className={`rounded-2xl border p-5 flex flex-col items-center text-center gap-2 ${card}`}>
                  <span className="h-10 w-10 rounded-full bg-emerald-500 text-white flex items-center justify-center font-bold" aria-hidden>✓</span>
                  <h2 className="text-lg font-bold">{t('warung_watch.thanks_title')}</h2>
                  <p className={`text-sm ${muted}`}>{fill(t('warung_watch.thanks_body'), { name: selected.name, status: t(levelKey(selected.crowd.status)) })}</p>
                </section>
              )}

              <section className={`rounded-2xl border p-5 flex flex-col gap-3 ${card}`}>
                <div>
                  <h2 className="text-lg font-bold">{selected.name}</h2>
                  <p className={`text-xs mt-1 ${muted}`}>
                    {[selected.location, selected.distance_m !== null ? fill(t('warung_watch.distance_m'), { n: selected.distance_m }) : null].filter(Boolean).join(' · ')}
                  </p>
                </div>
                {detailLoading && <div className={`h-24 rounded-xl animate-pulse ${isDark ? 'bg-white/10' : 'bg-zinc-100'}`} />}
                {detailError && (
                  <div>
                    <p className="font-semibold">{t('warung_watch.load_title')}</p>
                    <button type="button" onClick={() => void openPlace(selected)} className="mt-2 px-4 py-2 rounded-xl bg-nk-official text-white text-sm font-semibold">
                      {t('warung_watch.try_again')}
                    </button>
                  </div>
                )}
                {!detailLoading && !detailError && selected.crowd.status && (
                  <>
                    <div className={selected.crowd.is_fresh ? '' : 'opacity-70'}>
                      <p className="flex items-center gap-2 text-2xl font-bold">
                        <StatusMeter status={selected.crowd.status} stale={!selected.crowd.is_fresh} />
                        {t(levelKey(selected.crowd.status))}
                      </p>
                      <p className={`text-sm mt-1 ${muted}`}>{t(hintKey(selected.crowd.status))}</p>
                    </div>
                    <p className={`text-xs ${selected.crowd.is_fresh ? muted : 'text-amber-600 dark:text-amber-400'}`}>
                      {selected.crowd.is_fresh
                        ? `${fill(t('warung_watch.updated'), { time: formatAgo(selected.crowd.last_updated) })} · ${fill(t('warung_watch.reports_n'), { n: selected.crowd.report_count })}`
                        : fill(t('warung_watch.stale_age'), { time: formatAgo(selected.crowd.last_updated) })}
                    </p>
                  </>
                )}
                {!detailLoading && !detailError && !selected.crowd.status && (
                  <div>
                    <h3 className="font-semibold">{fill(t('warung_watch.no_reports_title'), { name: selected.name })}</h3>
                    <p className={`text-sm mt-1 ${muted}`}>{t('warung_watch.no_reports_body')}</p>
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <span className={`text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border ${isDark ? 'border-white/15' : 'border-zinc-200'}`}>{t('warung_watch.badge.community')}</span>
                  {selected.verified && (
                    <span className="text-[11px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border border-emerald-500/40 text-emerald-700 dark:text-emerald-300">
                      {t('warung_watch.badge.verified')}
                    </span>
                  )}
                </div>
              </section>

              {selected.crowd.status && selected.crowd.report_count > 0 && (
                <section className={`rounded-2xl border p-4 ${card}`}>
                  <div className="flex items-baseline justify-between gap-2">
                    <h3 className="text-sm font-semibold">{t('warung_watch.what_reported')}</h3>
                    <p className={`text-xs ${muted}`}>{fill(t('warung_watch.last_window'), { n: selected.crowd.report_count })}</p>
                  </div>
                  <ul className="mt-3 flex flex-col gap-2">
                    {(['empty', 'moderate', 'packed'] as CrowdStatus[]).map((status) => {
                      const count = selected.crowd.counts[status];
                      const width = selected.crowd.report_count > 0 ? Math.round((count / selected.crowd.report_count) * 100) : 0;
                      return (
                        <li key={status} className="grid grid-cols-[6rem_1fr_1.5rem] items-center gap-2 text-xs">
                          <span>{t(levelKey(status))}</span>
                          <span className="flex gap-0.5">
                            {Array.from({ length: 10 }, (_, index) => (
                              <span key={index} className={`h-1.5 flex-1 rounded-sm ${index < Math.round(width / 10) ? segmentClass(status, false) : isDark ? 'bg-white/10' : 'bg-zinc-100'}`} />
                            ))}
                          </span>
                          <span className="text-right">{count}</span>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              )}

              <section className={`rounded-2xl border p-4 ${card}`}>
                <h3 className="text-sm font-semibold">{t('warung_watch.typical_title')}</h3>
                <p className={`text-sm mt-1 ${muted}`}>
                  {selected.crowd.hour_status
                    ? fill(t('warung_watch.typical_value'), { status: t(levelKey(selected.crowd.hour_status)), n: selected.crowd.hour_reports })
                    : t('warung_watch.typical_empty')}
                </p>
              </section>

              {latestPrice && (
                <section className={`rounded-2xl border p-4 ${card}`}>
                  <h3 className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>{t('warung_watch.latest_price')}</h3>
                  <p className="mt-1 font-semibold">{latestPrice.price_item}</p>
                  <p className="text-sm">RM {latestPrice.price_myr.toFixed(2)} · {formatAgo(latestPrice.created_at)}</p>
                  {priceHistory.length >= 3 && <div className="mt-3"><WarungPriceChart history={priceHistory} isDark={isDark} /></div>}
                </section>
              )}

              <div className="flex gap-2">
                <a href={directionsUrl(selected)} target="_blank" rel="noreferrer" className={`flex-1 text-center px-4 py-3 rounded-xl border text-sm font-semibold ${isDark ? 'border-white/15' : 'border-zinc-200'}`}>
                  {t('warung_watch.directions')}
                </a>
                <button type="button" onClick={() => { setSheet(true); setReportError(false); }} className="flex-1 px-4 py-3 rounded-xl bg-nk-official text-white text-sm font-semibold">
                  {t('warung_watch.report_now')}
                </button>
              </div>

              {screen === 'thanks' && (
                <div className="flex flex-col gap-2">
                  <button type="button" onClick={() => { setScreen('home'); setPickForReport(false); if (coords) void fetchNearby(coords); }} className="px-4 py-3 rounded-xl bg-nk-official text-white text-sm font-semibold">
                    {t('warung_watch.back_nearby')}
                  </button>
                  <button type="button" onClick={() => void shareStatus()} className={`px-4 py-3 rounded-xl border text-sm font-semibold ${isDark ? 'border-white/15' : 'border-zinc-200'}`}>
                    {t('warung_watch.share')}
                  </button>
                </div>
              )}
            </div>
          )}
        </motion.div>

        {sheet && selected && (
          <div className="fixed inset-0 z-30 flex items-end sm:items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true" aria-labelledby="warung-report-title">
            <div className={`w-full max-w-md rounded-2xl border p-5 flex flex-col gap-3 ${isDark ? 'bg-[#1A1F2B] border-white/10 text-white' : 'bg-white border-zinc-200 text-zinc-900'}`}>
              <div className="flex items-start justify-between gap-3">
                <h2 id="warung-report-title" className="font-bold">{fill(t('warung_watch.sheet_title'), { name: selected.name })}</h2>
                <button type="button" onClick={() => setSheet(false)} className={`text-sm ${muted}`}>{t('warung_watch.close')}</button>
              </div>
              <p className={`text-sm ${muted}`}>{t('warung_watch.sheet_body')}</p>
              <div className="flex flex-col gap-2">
                {(['empty', 'moderate', 'packed'] as CrowdStatus[]).map((status) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => setReportStatus(status)}
                    className={`text-left rounded-xl border px-3 py-2 ${reportStatus === status ? 'border-nk-official bg-nk-official/10' : isDark ? 'border-white/10' : 'border-zinc-200'}`}
                  >
                    <span className="flex items-center gap-2 font-semibold text-sm">
                      <StatusMeter status={status} stale={false} />
                      {t(levelKey(status))}
                    </span>
                    <span className={`block text-xs mt-0.5 ${muted}`}>{t(hintKey(status))}</span>
                  </button>
                ))}
              </div>
              <div>
                <p className={`text-[11px] font-semibold uppercase tracking-wide mb-1.5 ${muted}`}>{t('warung_watch.price_label')}</p>
                <div className="flex gap-2">
                  <input value={priceItem} onChange={(event) => { setPriceItem(event.target.value); setPriceError(false); }} placeholder={t('warung_watch.price_item_placeholder')} maxLength={80} className={`flex-1 min-w-0 border rounded-lg px-3 py-2 text-xs bg-transparent ${isDark ? 'border-white/10' : 'border-zinc-200'}`} />
                  <input value={priceMyr} onChange={(event) => { setPriceMyr(event.target.value); setPriceError(false); }} inputMode="decimal" placeholder="RM" className={`w-20 border rounded-lg px-3 py-2 text-xs bg-transparent ${isDark ? 'border-white/10' : 'border-zinc-200'}`} />
                </div>
                {priceError && <p className="text-xs text-red-500 mt-1">{t('warung_watch.price_incomplete')}</p>}
              </div>
              {reportError && <p className="text-sm text-red-500">{t('warung_watch.report_failed')}</p>}
              <button type="button" disabled={!reportStatus || submitting} onClick={() => void submitReport()} className="px-4 py-3 rounded-xl bg-nk-official text-white text-sm font-semibold disabled:opacity-40">
                {reportError ? t('warung_watch.retry') : t('warung_watch.send_report')}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
