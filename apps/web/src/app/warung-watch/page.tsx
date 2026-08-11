'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { API_BASE } from '@/lib/api-base';
import { WarungPriceChart, type PriceHistoryPoint } from '@/components/warung-watch/WarungPriceChart';

const ANON_SESSION_KEY = 'naktahu_anon_session_id';

type Status = 'empty' | 'moderate' | 'packed';

interface WarungMatch {
  id: string;
  name: string;
  location: string | null;
  verified: boolean;
}

interface WarungStatus {
  warung: WarungMatch | null;
  status: Status | null;
  is_fresh: boolean;
  report_count: number;
  last_updated: string | null;
  sources: string[];
}

interface NearbyPlace {
  place_id: string | null;
  name: string;
  address: string | null;
  lat: number | null;
  lng: number | null;
}

const STATUS_STYLE: Record<Status, { emoji: string; bg: string; text: string }> = {
  empty: { emoji: '🟢', bg: 'bg-green-50 dark:bg-green-500/10 border-green-200 dark:border-green-500/30', text: 'text-green-700 dark:text-green-300' },
  moderate: { emoji: '🟡', bg: 'bg-amber-50 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/30', text: 'text-amber-700 dark:text-amber-300' },
  packed: { emoji: '🔴', bg: 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30', text: 'text-red-700 dark:text-red-300' },
};

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

  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<WarungMatch[]>([]);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [status, setStatus] = useState<WarungStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [priceHistory, setPriceHistory] = useState<PriceHistoryPoint[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  // Optional price report attached to a check-in — both must be filled to
  // submit (033_warung_checkin_price.sql's pair constraint).
  const [priceItem, setPriceItem] = useState('');
  const [priceMyr, setPriceMyr] = useState('');

  // "Nearby warungs" via the free browser Geolocation API + a Google Maps
  // search URL centered on the user's coords — no Google Places API key
  // needed, so the Maps link is fully functional regardless of backend
  // config. Alongside it, GET /api/v1/warung-watch/nearby calls the real
  // Places API (New) Nearby Search endpoint (see services/warung_watch.py)
  // to surface actual nearby place names as tappable buttons; it always
  // returns 200 with `configured: false` when GOOGLE_PLACES_API_KEY isn't
  // set on the backend, so this section degrades to the Maps-link-only
  // view rather than erroring.
  const [nearbyLoading, setNearbyLoading] = useState(false);
  const [nearbyMapsUrl, setNearbyMapsUrl] = useState<string | null>(null);
  const [nearbyError, setNearbyError] = useState<string | null>(null);
  const [nearbyPlaces, setNearbyPlaces] = useState<NearbyPlace[]>([]);
  const [nearbyPlacesConfigured, setNearbyPlacesConfigured] = useState(false);

  const findNearby = () => {
    if (typeof navigator === 'undefined' || !('geolocation' in navigator)) {
      setNearbyError(t('warung_watch.error.geolocation_unsupported'));
      return;
    }
    setNearbyLoading(true);
    setNearbyError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        setNearbyMapsUrl(`https://www.google.com/maps/search/warung+kedai+makan/@${latitude},${longitude},16z`);
        setNearbyLoading(false);
        apiFetch(`/api/v1/warung-watch/nearby?lat=${latitude}&lng=${longitude}`, accessToken)
          .then((res) => (res.ok ? res.json() : { configured: false, places: [] }))
          .then((data: { configured: boolean; places: NearbyPlace[] }) => {
            setNearbyPlacesConfigured(data.configured);
            setNearbyPlaces(data.places);
          })
          .catch(() => {
            // Search assist is a convenience on top of the Maps link above —
            // a failure here shouldn't block the flow that already worked.
          });
      },
      (err) => {
        // GeolocationPositionError.code: 1 = PERMISSION_DENIED, 2 =
        // POSITION_UNAVAILABLE, 3 = TIMEOUT — only code 1 is an actual
        // denial. The other two (including hitting the 10s timeout below)
        // were previously shown with the same "access denied" copy, which
        // told a user who simply had a slow GPS fix to go check their
        // permission settings instead of just retrying.
        setNearbyError(
          err.code === GeolocationPositionError.PERMISSION_DENIED
            ? t('warung_watch.error.geolocation_denied')
            : t('warung_watch.error.geolocation_unavailable'),
        );
        setNearbyLoading(false);
      },
      { timeout: 10000 },
    );
  };

  const selectNearbyPlace = (name: string) => {
    setQuery(name);
    void loadStatus(name);
  };

  useEffect(() => {
    if (!localStorage.getItem(ANON_SESSION_KEY)) {
      localStorage.setItem(ANON_SESSION_KEY, crypto.randomUUID());
    }
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    let active = true;
    const timeout = setTimeout(() => {
      apiFetch(`/api/v1/warung-watch/search?q=${encodeURIComponent(query)}`, accessToken)
        .then((res) => (res.ok ? res.json() : []))
        .then((data: WarungMatch[]) => {
          if (active) setSuggestions(data);
        })
        .catch(() => {
          /* Search suggestions are a convenience — a failure shouldn't block typing */
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timeout);
    };
  }, [query, accessToken]);

  const loadStatus = async (name: string) => {
    setStatusLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/warung-watch/status?name=${encodeURIComponent(name)}`, accessToken);
      if (!res.ok) throw new Error('fetch-failed');
      const data: WarungStatus = await res.json();
      setStatus(data);
      setSelectedName(name);
      setSuggestions([]);
      // Price history is a convenience add-on to the status card — a
      // failure here shouldn't block the busyness status the user
      // actually asked for, so it's fetched separately and not awaited
      // as part of the try/catch above.
      setPriceHistory([]);
      apiFetch(`/api/v1/warung-watch/price-history?name=${encodeURIComponent(name)}`, accessToken)
        .then((r) => (r.ok ? r.json() : { history: [] }))
        .then((d: { history: PriceHistoryPoint[] }) => setPriceHistory(d.history))
        .catch(() => {
          /* chart just stays empty — see WarungPriceChart's empty-state handling */
        });
    } catch {
      setError(t('warung_watch.error.fetch'));
    } finally {
      setStatusLoading(false);
    }
  };

  const submitCheckin = async (checkinStatus: Status) => {
    const name = (selectedName ?? query).trim();
    if (!name) return;
    // Price report is optional and both fields must be filled together —
    // mirrors 033_warung_checkin_price.sql's warung_checkins_price_pair_chk
    // constraint. Silently drop a half-filled pair rather than let the
    // backend 422 on a field the user never meant to submit.
    const trimmedPriceItem = priceItem.trim();
    const parsedPrice = priceMyr.trim() ? Number(priceMyr) : null;
    const hasCompletePricePair = trimmedPriceItem !== '' && parsedPrice !== null && !Number.isNaN(parsedPrice);

    setSubmitting(true);
    setError(null);
    try {
      const res = await apiFetch('/api/v1/warung-watch/checkin', accessToken, {
        method: 'POST',
        body: JSON.stringify({
          name,
          status: checkinStatus,
          anon_session_id: localStorage.getItem(ANON_SESSION_KEY),
          ...(hasCompletePricePair ? { price_item: trimmedPriceItem, price_myr: parsedPrice } : {}),
        }),
      });
      if (!res.ok) throw new Error('submit-failed');
      setSubmitted(true);
      setPriceItem('');
      setPriceMyr('');
      await loadStatus(name);
    } catch {
      setError(t('warung_watch.error.submit'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`flex h-full ${isDark ? 'bg-[#0A0F1E] text-white' : 'bg-zinc-50/50 text-zinc-900'}`}>
      <AppSidebar
        variant={isDark ? 'dark' : 'light'}
        isMobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        user={user}
        accessToken={accessToken}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
      />

      <div className="flex flex-col flex-1 min-w-0 h-full overflow-y-auto">
        <header
          className={`flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b backdrop-blur-md sticky top-0 z-10 shadow-sm ${
            isDark ? 'border-white/10 bg-[#0A0F1E]/90 text-white' : 'border-zinc-100 bg-white/90 text-zinc-900'
          }`}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label={t('header.menu')}
            className={`p-1.5 rounded-lg transition-colors lg:hidden ${
              isDark ? 'text-zinc-400 hover:bg-white/10 hover:text-zinc-200' : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800'
            }`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
              <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
            </svg>
          </button>
          <Link href="/" className="flex flex-col">
            <span className="text-base font-bold tracking-tight">{t('header.title')}</span>
            <span className={`text-xs ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{t('header.subtitle')}</span>
          </Link>
        </header>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="max-w-xl mx-auto px-4 py-8 w-full flex flex-col gap-5"
        >
          <div>
            <h1 className="text-lg font-bold">{t('warung_watch.title')}</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">{t('warung_watch.desc')}</p>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
              {error}
            </div>
          )}

          <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-2 shadow-sm dark:bg-white/5 dark:border-white/10">
            <h2 className="text-sm font-semibold">{t('warung_watch.nearby_title')}</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('warung_watch.nearby_desc')}</p>
            {nearbyError && <p className="text-xs text-red-600 dark:text-red-400">{nearbyError}</p>}
            {nearbyMapsUrl ? (
              <a
                href={nearbyMapsUrl}
                target="_blank"
                rel="noreferrer"
                className="self-start inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 transition-colors text-white text-sm font-semibold"
              >
                🗺️ {t('warung_watch.nearby_open_maps')}
              </a>
            ) : (
              <button
                type="button"
                disabled={nearbyLoading}
                onClick={findNearby}
                className="self-start px-4 py-2 rounded-xl border border-orange-300 text-orange-700 dark:text-orange-300 dark:border-orange-500/40 hover:bg-orange-50 dark:hover:bg-orange-500/10 transition-colors text-sm font-semibold disabled:opacity-50"
              >
                {nearbyLoading ? t('warung_watch.nearby_locating') : t('warung_watch.nearby_button')}
              </button>
            )}
            {nearbyMapsUrl && nearbyPlacesConfigured && nearbyPlaces.length > 0 && (
              <div className="flex flex-col gap-1.5 pt-1">
                <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {t('warung_watch.nearby_places_title')}
                </p>
                <ul className="flex flex-col gap-1.5">
                  {nearbyPlaces.map((place) => (
                    <li key={place.place_id ?? place.name}>
                      <button
                        type="button"
                        onClick={() => selectNearbyPlace(place.name)}
                        className="w-full text-left px-3 py-2 rounded-lg border border-zinc-200 dark:border-white/10 text-sm hover:bg-zinc-50 dark:hover:bg-white/5 transition-colors"
                      >
                        {place.name}
                        {place.address && <span className="block text-xs text-zinc-400">{place.address}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <section className="relative bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
            <label className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              {t('warung_watch.search_label')}
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedName(null);
                setStatus(null);
                setSubmitted(false);
              }}
              placeholder={t('warung_watch.search_placeholder')}
              className="w-full border border-zinc-200 rounded-xl p-3 text-sm bg-transparent focus:outline-none focus:border-orange-400 dark:border-white/10 dark:placeholder:text-zinc-500"
            />
            {suggestions.length > 0 && (
              <ul className="absolute left-5 right-5 top-full mt-1 bg-white dark:bg-[#111827] border border-zinc-200 dark:border-white/10 rounded-xl shadow-lg overflow-hidden z-20">
                {suggestions.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setQuery(s.name);
                        void loadStatus(s.name);
                      }}
                      className="w-full text-left px-4 py-2.5 text-sm hover:bg-zinc-50 dark:hover:bg-white/5 transition-colors"
                    >
                      {s.name}
                      {s.location && <span className="text-zinc-400 text-xs ml-2">{s.location}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              disabled={!query.trim() || statusLoading}
              onClick={() => void loadStatus(query.trim())}
              className="self-end px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 transition-colors text-white text-sm font-semibold disabled:opacity-50"
            >
              {statusLoading ? t('warung_watch.checking') : t('warung_watch.check_status')}
            </button>
          </section>

          {status && (
            <section
              className={`rounded-2xl border-2 p-5 ${status.status ? STATUS_STYLE[status.status].bg : 'bg-zinc-50 dark:bg-white/5 border-zinc-200 dark:border-white/10'}`}
            >
              {status.status ? (
                <>
                  <p className={`text-2xl ${STATUS_STYLE[status.status].text}`} aria-hidden>{STATUS_STYLE[status.status].emoji}</p>
                  <p className={`mt-1 font-bold text-lg ${STATUS_STYLE[status.status].text}`}>
                    {t(`warung_watch.status.${status.status}`)}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                    {t('warung_watch.report_count').replace('{n}', String(status.report_count))}
                    {!status.is_fresh && ` · ${t('warung_watch.stale_note')}`}
                  </p>
                </>
              ) : (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('warung_watch.no_reports')}</p>
              )}
            </section>
          )}

          {priceHistory.length > 0 && (
            <section className="bg-white rounded-2xl border border-zinc-200 p-5 shadow-sm dark:bg-white/5 dark:border-white/10">
              <WarungPriceChart history={priceHistory} isDark={isDark} />
            </section>
          )}

          <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
            <h2 className="text-sm font-semibold">{t('warung_watch.checkin_prompt')}</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('warung_watch.checkin_hint')}</p>
            <div className="grid grid-cols-3 gap-2">
              {(['empty', 'moderate', 'packed'] as Status[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={!query.trim() || submitting}
                  onClick={() => void submitCheckin(s)}
                  className={`flex flex-col items-center gap-1 rounded-xl border p-3 text-xs font-semibold transition-colors disabled:opacity-40 ${STATUS_STYLE[s].bg} ${STATUS_STYLE[s].text} hover:brightness-95`}
                >
                  <span className="text-lg" aria-hidden>{STATUS_STYLE[s].emoji}</span>
                  {t(`warung_watch.status.${s}`)}
                </button>
              ))}
            </div>

            <div className="pt-1 border-t border-zinc-100 dark:border-white/10">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1.5 mt-2">
                {t('warung_watch.price_label')}
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={priceItem}
                  onChange={(e) => setPriceItem(e.target.value)}
                  placeholder={t('warung_watch.price_item_placeholder')}
                  maxLength={80}
                  className="flex-1 min-w-0 border border-zinc-200 rounded-lg px-3 py-2 text-xs bg-transparent focus:outline-none focus:border-orange-400 dark:border-white/10 dark:placeholder:text-zinc-500"
                />
                <input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  step={0.1}
                  value={priceMyr}
                  onChange={(e) => setPriceMyr(e.target.value)}
                  placeholder="RM"
                  className="w-20 border border-zinc-200 rounded-lg px-3 py-2 text-xs bg-transparent focus:outline-none focus:border-orange-400 dark:border-white/10 dark:placeholder:text-zinc-500"
                />
              </div>
              <p className="text-[11px] text-zinc-400 mt-1">{t('warung_watch.price_hint')}</p>
            </div>

            {submitted && (
              <p className="text-xs text-green-600 dark:text-green-400">{t('warung_watch.checkin_success')}</p>
            )}
          </section>
        </motion.div>
      </div>
    </div>
  );
}
