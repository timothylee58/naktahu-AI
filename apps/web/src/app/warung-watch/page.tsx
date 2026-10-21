'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { BadgeCheck, Check, Clock, MapPin, Menu, Navigation } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { NakTahuWordmark } from '@/components/logo/NakTahuWordmark';
import { Button, buttonVariants } from '@/components/ui/button';
import { API_BASE } from '@/lib/api-base';
import { WarungPriceChart, type PriceHistoryPoint } from '@/components/warung-watch/WarungPriceChart';
import { PlaceCard } from '@/components/warung-watch/PlaceCard';
import { PlaceSearch } from '@/components/warung-watch/PlaceSearch';
import { ReportSheet } from '@/components/warung-watch/ReportSheet';
import { StatusMeter } from '@/components/warung-watch/StatusMeter';
import { cn } from '@/lib/utils';
import {
  asCrowd,
  directionsUrl,
  EMPTY_CROWD,
  FILL_CLASS,
  fill,
  freshnessTone,
  haversineM,
  hintKey,
  levelKey,
  normName,
  STATUSES,
  TEXT_CLASS,
  type Coords,
  type CrowdStatus,
  type Place,
} from '@/lib/warung-watch/crowd';

const ANON_SESSION_KEY = 'naktahu_anon_session_id';
const RADIUS_M = 800;

type Screen = 'home' | 'detail' | 'thanks';

async function apiFetch(path: string, accessToken: string | null, init?: RequestInit) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  return fetch(`${API_BASE}${path}`, { ...init, headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) } });
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
          distance = haversineM(next, { lat: place.lat, lng: place.lng });
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

  const latestPrice = priceHistory.length > 0 ? priceHistory[priceHistory.length - 1] : null;



  const announce = locating
    ? t('warung_watch.nearby_locating')
    : browsing === 'list' && places.length > 0
      ? fill(t('warung_watch.results_count'), { n: visiblePlaces.length })
      : '';

  const closeDetail = () => {
    setScreen('home');
    setSheet(false);
    setPickForReport(false);
  };

  const openReport = () => {
    setSheet(true);
    setReportError(false);
  };

  const actions = selected && (
    <>
      <a
        href={directionsUrl(selected)}
        target="_blank"
        rel="noreferrer"
        className={cn(buttonVariants({ variant: 'outline' }), 'h-12 flex-1 text-base sm:text-sm')}
      >
        <Navigation className="h-4 w-4" aria-hidden />
        {t('warung_watch.directions')}
      </a>
      <Button type="button" className="h-12 flex-1 text-base sm:text-sm" onClick={openReport}>
        {t('warung_watch.report_now')}
      </Button>
    </>
  );

  const crowd = selected?.crowd;
  const tone = crowd ? freshnessTone(crowd) : 'none';

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
      <div className="flex h-full min-w-0 flex-1 flex-col overflow-y-auto">
        <header
          className={`sticky top-0 z-10 flex flex-shrink-0 items-center gap-2 border-b px-4 py-2 backdrop-blur-md ${
            isDark ? 'border-white/10 bg-[#12151C]/90 text-white' : 'border-zinc-100 bg-white/90 text-zinc-900'
          }`}
        >
          <Button type="button" variant="ghost" size="icon" onClick={() => setSidebarOpen(true)} aria-label={t('header.menu')} className="-ml-2 h-11 w-11 lg:hidden">
            <Menu className="h-5 w-5" aria-hidden />
          </Button>
          <Link href="/" className="flex min-h-11 flex-col justify-center">
            <NakTahuWordmark markSize={20} className="text-base" />
            <span className="text-xs text-nk-muted-aa">{t('header.subtitle')}</span>
          </Link>
        </header>

        <p className="sr-only" role="status" aria-live="polite">{announce}</p>

        <motion.main
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn(
            'mx-auto w-full max-w-md px-4 py-6 lg:grid lg:max-w-6xl lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:items-start lg:gap-8 lg:px-8',
            screen !== 'home' && 'pb-28 lg:pb-6',
          )}
        >
          <section aria-label={t('warung_watch.title')} className={cn('flex-col gap-4', screen === 'home' ? 'flex' : 'hidden lg:flex')}>
            <div>
              <h1 className="font-display text-2xl font-bold text-nk-ink">{t('warung_watch.title')}</h1>
              <p className="mt-1 text-sm text-nk-muted-aa">{t('warung_watch.lede')}</p>
              <span className="mt-2 inline-block rounded-full border border-nk-community/40 bg-[var(--nk-fill-community)] px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-nk-community-text">
                {t('warung_watch.badge.community')}
              </span>
            </div>

            {browsing === 'list' && coords && (
              <div className="flex items-center justify-between gap-3 text-sm">
                <p className="text-nk-ink">{fill(t('warung_watch.within'), { m: RADIUS_M })}</p>
                <Button type="button" variant="ghost" className="h-11 px-3 text-nk-official-text" onClick={() => setBrowsing('search')}>
                  {t('warung_watch.change')}
                </Button>
              </div>
            )}

            {(browsing === 'ask' || browsing === 'search') && (
              <section className="flex flex-col gap-3 rounded-2xl border border-[var(--nk-border)] bg-nk-card p-4">
                {browsing === 'ask' && (
                  <>
                    <h2 className="font-semibold text-nk-ink">{t('warung_watch.location_off_title')}</h2>
                    <p className="text-sm text-nk-muted-aa">{t('warung_watch.location_off_body')}</p>
                    <Button type="button" onClick={loadNearby} disabled={locating} className="h-12 w-full text-base sm:text-sm">
                      <MapPin className="h-4 w-4" aria-hidden />
                      {locating ? t('warung_watch.nearby_locating') : t('warung_watch.use_location')}
                    </Button>
                  </>
                )}
                <PlaceSearch
                  query={query}
                  onQueryChange={setQuery}
                  suggestions={suggestions}
                  onPick={(place) => void openPlace(place, { report: pickForReport })}
                  onAddNew={(name) =>
                    void openPlace(
                      { key: `new:${normName(name)}`, name, location: null, verified: false, lat: null, lng: null, distance_m: null, crowd: EMPTY_CROWD },
                      { report: pickForReport },
                    )
                  }
                  hint={pickForReport ? t('warung_watch.pick_place') : undefined}
                  inputRef={searchRef}
                  t={t}
                />
              </section>
            )}

            {browsing === 'list' && (
              <section className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--nk-border)] bg-nk-card p-4">
                <div>
                  <h2 className="text-sm font-semibold text-nk-ink">{t('warung_watch.here_title')}</h2>
                  <p className="mt-1 text-xs text-nk-muted-aa">{t('warung_watch.here_body')}</p>
                </div>
                <Button
                  type="button"
                  className="h-11 shrink-0"
                  onClick={() => {
                    setPickForReport(true);
                    setBrowsing('search');
                    setTimeout(() => searchRef.current?.focus(), 0);
                  }}
                >
                  {t('warung_watch.report')}
                </Button>
              </section>
            )}

            {locating && (
              <div className="flex flex-col gap-2" aria-hidden>
                {[0, 1, 2].map((row) => (
                  <div key={row} className="h-[4.5rem] rounded-2xl bg-[var(--nk-track)]" />
                ))}
              </div>
            )}

            {listError && (
              <section role="alert" className="flex flex-col gap-2 rounded-2xl border border-[var(--nk-border)] bg-nk-card p-4">
                <h2 className="font-semibold text-nk-ink">{t('warung_watch.load_title')}</h2>
                <p className="text-sm text-nk-muted-aa">{t('warung_watch.load_body')}</p>
                <Button type="button" onClick={loadNearby} className="h-11 self-start">
                  {t('warung_watch.try_again')}
                </Button>
              </section>
            )}

            {browsing === 'list' && !locating && places.length > 0 && (
              <div className="flex justify-end">
                <button
                  type="button"
                  aria-pressed={quietOnly}
                  onClick={() => setQuietOnly((current) => !current)}
                  className={cn(
                    'min-h-11 rounded-full border px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official',
                    quietOnly ? 'border-nk-quiet bg-nk-quiet text-white' : 'border-[var(--nk-border)] text-nk-ink hover:border-nk-official/40',
                  )}
                >
                  {t('warung_watch.quiet_only')}
                </button>
              </div>
            )}

            {browsing === 'list' && !locating && quietOnly && places.length > 0 && visiblePlaces.length === 0 && (
              <section className="flex flex-col gap-2 rounded-2xl border border-[var(--nk-border)] bg-nk-card p-4">
                <h2 className="font-semibold text-nk-ink">{t('warung_watch.nothing_quiet_title')}</h2>
                <p className="text-sm text-nk-muted-aa">{t('warung_watch.nothing_quiet_body')}</p>
                <Button type="button" onClick={() => setQuietOnly(false)} className="h-11 self-start">
                  {t('warung_watch.show_all')}
                </Button>
              </section>
            )}

            {browsing === 'list' && !locating && places.length === 0 && !listError && (
              <section className="rounded-2xl border border-[var(--nk-border)] bg-nk-card p-4">
                <h2 className="font-semibold text-nk-ink">{t('warung_watch.none_nearby_title')}</h2>
                <p className="mt-1 text-sm text-nk-muted-aa">{t('warung_watch.none_nearby_body')}</p>
              </section>
            )}

            {browsing === 'list' && !locating && (
              <ul className="flex flex-col gap-2">
                {visiblePlaces.map((place) => (
                  <li key={place.key}>
                    <PlaceCard place={place} t={t} formatAgo={formatAgo} onOpen={(next) => void openPlace(next)} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-label={selected?.name ?? t('warung_watch.pick_place_title')} className={cn('flex-col gap-4 lg:sticky lg:top-20', screen === 'home' ? 'hidden lg:flex' : 'flex')}>
            {!selected && (
              <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-[var(--nk-border)] p-8 text-center">
                <MapPin className="h-8 w-8 text-nk-muted-aa" aria-hidden />
                <h2 className="font-semibold text-nk-ink">{t('warung_watch.pick_place_title')}</h2>
                <p className="max-w-xs text-sm text-nk-muted-aa">{t('warung_watch.pick_place_body')}</p>
              </div>
            )}

            {selected && (
              <>
                <Button type="button" variant="ghost" className="-ml-3 h-11 self-start px-3 text-nk-muted-aa lg:hidden" onClick={closeDetail}>
                  ← {t('warung_watch.back')}
                </Button>

                {screen === 'thanks' && crowd?.status && (
                  <section role="status" className="flex flex-col items-center gap-2 rounded-2xl border border-[var(--nk-border)] bg-nk-card p-5 text-center">
                    <span className="flex h-11 w-11 items-center justify-center rounded-full bg-nk-quiet text-white">
                      <Check className="h-6 w-6" aria-hidden />
                    </span>
                    <h2 className="text-lg font-bold text-nk-ink">{t('warung_watch.thanks_title')}</h2>
                    <p className="text-sm text-nk-muted-aa">
                      {fill(t('warung_watch.thanks_body'), { name: selected.name, status: t(levelKey(crowd.status)) })}
                    </p>
                  </section>
                )}

                <section className="flex flex-col gap-3 rounded-2xl border border-[var(--nk-border)] bg-nk-card p-5" aria-busy={detailLoading}>
                  <div>
                    <h2 className="font-display text-xl font-bold text-nk-ink">{selected.name}</h2>
                    <p className="mt-1 text-sm text-nk-muted-aa">
                      {[selected.location, selected.distance_m !== null ? fill(t('warung_watch.distance_m'), { n: selected.distance_m }) : null].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                  {detailLoading && <div className="h-24 rounded-xl bg-[var(--nk-track)]" aria-hidden />}
                  {detailError && (
                    <div role="alert">
                      <p className="font-semibold text-nk-ink">{t('warung_watch.load_title')}</p>
                      <Button type="button" className="mt-2 h-11" onClick={() => void openPlace(selected)}>
                        {t('warung_watch.try_again')}
                      </Button>
                    </div>
                  )}
                  {!detailLoading && !detailError && crowd?.status && (
                    <>
                      <div className={cn('flex items-center gap-4', tone === 'stale' && 'opacity-75')}>
                        <StatusMeter status={crowd.status} stale={tone === 'stale'} size="lg" />
                        <div>
                          <p className={cn('text-2xl font-bold', tone === 'stale' ? 'text-nk-muted-aa' : TEXT_CLASS[crowd.status])}>{t(levelKey(crowd.status))}</p>
                          <p className="text-sm text-nk-muted-aa">{t(hintKey(crowd.status))}</p>
                        </div>
                      </div>
                      <p className={cn('flex items-center gap-1.5 font-mono text-xs', tone === 'stale' ? 'text-nk-moderate-text' : 'text-nk-muted-aa')}>
                        <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden />
                        <time dateTime={crowd.last_updated ?? undefined}>
                          {tone === 'fresh'
                            ? `${fill(t('warung_watch.updated'), { time: formatAgo(crowd.last_updated) })} · ${fill(t('warung_watch.reports_n'), { n: crowd.report_count })}`
                            : fill(t('warung_watch.stale_age'), { time: formatAgo(crowd.last_updated) })}
                        </time>
                      </p>
                    </>
                  )}
                  {!detailLoading && !detailError && !crowd?.status && (
                    <div>
                      <h3 className="font-semibold text-nk-ink">{fill(t('warung_watch.no_reports_title'), { name: selected.name })}</h3>
                      <p className="mt-1 text-sm text-nk-muted-aa">{t('warung_watch.no_reports_body')}</p>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full border border-nk-community/40 bg-[var(--nk-fill-community)] px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-nk-community-text">
                      {t('warung_watch.badge.community')}
                    </span>
                    {selected.verified && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-nk-quiet/40 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-nk-quiet-text">
                        <BadgeCheck className="h-3.5 w-3.5" aria-hidden />
                        {t('warung_watch.badge.verified')}
                      </span>
                    )}
                  </div>
                </section>

                {crowd?.status && crowd.report_count > 0 && (
                  <section className="rounded-2xl border border-[var(--nk-border)] bg-nk-card p-4">
                    <div className="flex items-baseline justify-between gap-2">
                      <h3 className="text-sm font-semibold text-nk-ink">{t('warung_watch.what_reported')}</h3>
                      <p className="text-xs text-nk-muted-aa">{fill(t('warung_watch.last_window'), { n: crowd.report_count })}</p>
                    </div>
                    <ul className="mt-3 flex flex-col gap-2.5">
                      {STATUSES.map((status: CrowdStatus) => {
                        const count = crowd.counts[status];
                        const tenths = crowd.report_count > 0 ? Math.round((count / crowd.report_count) * 10) : 0;
                        return (
                          <li key={status} className="grid grid-cols-[6rem_1fr_1.5rem] items-center gap-2 text-sm text-nk-ink">
                            <span>{t(levelKey(status))}</span>
                            <span className="flex gap-0.5" aria-hidden>
                              {Array.from({ length: 10 }, (_, index) => (
                                <span key={index} className={cn('h-2 flex-1 rounded-sm', index < tenths ? FILL_CLASS[status] : 'bg-[var(--nk-track)]')} />
                              ))}
                            </span>
                            <span className="text-right tabular-nums">{count}</span>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                )}

                <section className="rounded-2xl border border-[var(--nk-border)] bg-nk-card p-4">
                  <h3 className="text-sm font-semibold text-nk-ink">{t('warung_watch.typical_title')}</h3>
                  <p className="mt-1 text-sm text-nk-muted-aa">
                    {crowd?.hour_status
                      ? fill(t('warung_watch.typical_value'), { status: t(levelKey(crowd.hour_status)), n: crowd.hour_reports })
                      : t('warung_watch.typical_empty')}
                  </p>
                </section>

                {latestPrice && (
                  <section className="rounded-2xl border border-[var(--nk-border)] bg-nk-card p-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-nk-muted-aa">{t('warung_watch.latest_price')}</h3>
                    <p className="mt-1 font-semibold text-nk-ink">{latestPrice.price_item}</p>
                    <p className="text-sm text-nk-ink">RM {latestPrice.price_myr.toFixed(2)} · {formatAgo(latestPrice.created_at)}</p>
                    {priceHistory.length >= 3 && <div className="mt-3"><WarungPriceChart history={priceHistory} isDark={isDark} /></div>}
                  </section>
                )}

                <div className="hidden gap-2 lg:flex">{actions}</div>

                {screen === 'thanks' && (
                  <div className="flex flex-col gap-2">
                    <Button
                      type="button"
                      className="h-12 text-base lg:hidden"
                      onClick={() => {
                        closeDetail();
                        if (coords) void fetchNearby(coords);
                      }}
                    >
                      {t('warung_watch.back_nearby')}
                    </Button>
                    <Button type="button" variant="outline" className="h-12 text-base sm:text-sm" onClick={() => void shareStatus()}>
                      {t('warung_watch.share')}
                    </Button>
                  </div>
                )}
              </>
            )}
          </section>
        </motion.main>

        {selected && screen !== 'home' && !sheet && (
          <div className="fixed inset-x-0 bottom-0 z-20 flex gap-2 border-t border-[var(--nk-border)] bg-nk-card/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur lg:hidden">
            {actions}
          </div>
        )}

        <ReportSheet
          open={sheet && Boolean(selected)}
          placeName={selected?.name ?? ''}
          status={reportStatus}
          onStatus={setReportStatus}
          priceItem={priceItem}
          priceMyr={priceMyr}
          onPriceItem={(value) => { setPriceItem(value); setPriceError(false); }}
          onPriceMyr={(value) => { setPriceMyr(value); setPriceError(false); }}
          priceError={priceError}
          reportError={reportError}
          submitting={submitting}
          onSubmit={() => void submitReport()}
          onClose={() => setSheet(false)}
          t={t}
        />
      </div>
    </div>
  );
}
