'use client';

import { useEffect, useState } from 'react';
import { useI18n } from '@/lib/i18n';
import { useAgentApi } from '@/lib/hooks/useAgentApi';

// The legitimate alternative to property_concierge sourcing live listings
// itself (see that agent's module docstring) — the user pastes a listing
// URL + details they found themselves. The credit reward is disclosed
// right on the form (not concealed) and is idempotent server-side per
// (user, url) — see services/property_submissions.py.
interface Listing {
  id: string;
  url: string;
  title?: string | null;
  price_myr?: number | null;
  location?: string | null;
  status: string;
  created_at: string;
}

type SubmitStatus =
  | { kind: 'idle' }
  | { kind: 'success'; alreadySubmitted: boolean }
  | { kind: 'error'; message: string };

export function PropertyListingSubmitCard() {
  const { t } = useI18n();
  const { post, get } = useAgentApi();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [priceMyr, setPriceMyr] = useState('');
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<SubmitStatus>({ kind: 'idle' });
  const [listings, setListings] = useState<Listing[]>([]);

  const loadListings = () => {
    void get('/api/v1/property/listings/mine')
      .then((res) => setListings((res.listings as Listing[]) ?? []))
      .catch(() => {
        /* best-effort — the form still works without the history list */
      });
  };

  useEffect(() => {
    if (open) loadListings();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setStatus({ kind: 'idle' });
    try {
      const res = await post('/api/v1/property/listings', {
        url: url.trim(),
        title: title.trim() || undefined,
        price_myr: priceMyr.trim() ? Number(priceMyr.trim()) : undefined,
        location: location.trim() || undefined,
      });
      setStatus({ kind: 'success', alreadySubmitted: !res.submitted });
      setUrl('');
      setTitle('');
      setPriceMyr('');
      setLocation('');
      loadListings();
    } catch {
      setStatus({ kind: 'error', message: t('agents.property-concierge.submit.error') });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 dark:bg-white/5 dark:border-white/10">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center justify-between text-left"
      >
        <span className="text-sm font-semibold">{t('agents.property-concierge.submit.title')}</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`w-4 h-4 text-zinc-400 transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
        </svg>
      </button>

      {open && (
        <>
          {/* Disclosed, not hidden — stated plainly right on the form. */}
          <p className="text-xs text-lime-700 bg-lime-50 border border-lime-100 rounded-lg px-3 py-2 dark:text-lime-300 dark:bg-lime-500/10 dark:border-lime-500/30">
            {t('agents.property-concierge.submit.incentive')}
          </p>

          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={t('agents.property-concierge.submit.url_placeholder')}
            className="border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-lime-500/50 dark:border-white/10 dark:placeholder:text-zinc-500"
          />
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t('agents.property-concierge.submit.title_placeholder')}
              className="border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-lime-500/50 dark:border-white/10 dark:placeholder:text-zinc-500"
            />
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder={t('agents.property-concierge.submit.location_placeholder')}
              className="border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-lime-500/50 dark:border-white/10 dark:placeholder:text-zinc-500"
            />
          </div>
          <input
            type="number"
            min={0}
            value={priceMyr}
            onChange={(e) => setPriceMyr(e.target.value)}
            placeholder={t('agents.property-concierge.submit.price_placeholder')}
            className="border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-lime-500/50 dark:border-white/10 dark:placeholder:text-zinc-500"
          />

          <button
            type="button"
            disabled={loading || !url.trim()}
            onClick={() => void submit()}
            className="self-end px-4 py-2 bg-lime-600 hover:bg-lime-500 text-white rounded-xl text-sm font-semibold transition-colors disabled:opacity-50"
          >
            {loading ? t('agents.property-concierge.submit.submitting') : t('agents.property-concierge.submit.button')}
          </button>

          {status.kind === 'success' && (
            <p className="text-xs font-medium text-green-600 dark:text-green-400">
              {status.alreadySubmitted
                ? t('agents.property-concierge.submit.already_submitted')
                : t('agents.property-concierge.submit.success')}
            </p>
          )}
          {status.kind === 'error' && (
            <p className="text-xs font-medium text-red-600 dark:text-red-400">{status.message}</p>
          )}

          {listings.length > 0 && (
            <div className="flex flex-col gap-1.5 mt-1 pt-3 border-t border-zinc-100 dark:border-white/10">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                {t('agents.property-concierge.submit.my_listings')}
              </p>
              {listings.map((l) => (
                <a
                  key={l.id}
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-nk-official-dim hover:text-nk-official truncate transition-colors"
                >
                  {l.title || l.url}
                </a>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
