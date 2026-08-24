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
  | { kind: 'error'; message: string }
  | { kind: 'ocr_filled' }
  | { kind: 'ocr_error' };

const MAX_UPLOAD_BYTES = 6 * 1024 * 1024; // matches the backend's ~6.7MB decoded ceiling

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      // reader.result is "data:<mime>;base64,<data>" — the API wants just <data>.
      const result = reader.result as string;
      const comma = result.indexOf(',');
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function PropertyListingSubmitCard() {
  const { t, locale } = useI18n();
  const { post, get } = useAgentApi();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [priceMyr, setPriceMyr] = useState('');
  const [location, setLocation] = useState('');
  const [propertyType, setPropertyType] = useState('');
  const [bedrooms, setBedrooms] = useState('');
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
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
        property_type: propertyType || undefined,
        bedrooms: bedrooms.trim() ? Number(bedrooms.trim()) : undefined,
      });
      setStatus({ kind: 'success', alreadySubmitted: !res.submitted });
      setUrl('');
      setTitle('');
      setPriceMyr('');
      setLocation('');
      setPropertyType('');
      setBedrooms('');
      loadListings();
    } catch {
      setStatus({ kind: 'error', message: t('agents.property-concierge.submit.error') });
    } finally {
      setLoading(false);
    }
  };

  // Photo/screenshot → OCR prefill. Never submits anything itself — it only
  // fills the form fields above, which the user still reviews and confirms
  // via the existing submit() path (see services/property_submissions.py's
  // extract_listing_from_image docstring for why: OCR-sourced text is no
  // more trusted than manually-typed text until the user has looked at it).
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file later
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setStatus({ kind: 'ocr_error' });
      return;
    }
    setScanning(true);
    setStatus({ kind: 'idle' });
    try {
      const imageBase64 = await fileToBase64(file);
      const backendLang = locale === 'ms' ? 'bm' : locale;
      const res = await post('/api/v1/property/listings/ocr', {
        image_base64: imageBase64,
        mime_type: file.type || 'image/jpeg',
        language: backendLang,
      });
      const fields = (res.fields ?? {}) as Record<string, unknown>;
      if (Object.keys(fields).length === 0) {
        setStatus({ kind: 'ocr_error' });
        return;
      }
      if (typeof fields.title === 'string') setTitle(fields.title);
      if (typeof fields.location === 'string') setLocation(fields.location);
      if (typeof fields.price_myr === 'number') setPriceMyr(String(fields.price_myr));
      if (typeof fields.property_type === 'string') setPropertyType(fields.property_type);
      if (typeof fields.bedrooms === 'number') setBedrooms(String(fields.bedrooms));
      setStatus({ kind: 'ocr_filled' });
    } catch {
      setStatus({ kind: 'ocr_error' });
    } finally {
      setScanning(false);
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

          <label className="flex items-center justify-center gap-2 border border-dashed border-zinc-300 rounded-xl p-2.5 text-sm text-zinc-500 cursor-pointer hover:border-lime-500/50 hover:text-lime-700 transition-colors dark:border-white/15 dark:text-zinc-400 dark:hover:text-lime-300">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 flex-shrink-0">
              <path fillRule="evenodd" d="M15.988 3.012A2.25 2.25 0 0 1 18 5.25v6.5A2.25 2.25 0 0 1 15.75 14H4.25A2.25 2.25 0 0 1 2 11.75v-6.5a2.25 2.25 0 0 1 2.25-2.238h11.738ZM6.75 8.25a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z" clipRule="evenodd" />
              <path d="M3.5 12.5 7 9l2 2 3.5-4L16.5 12v-.75a.75.75 0 0 0-1.5 0V12.5h-11.5Z" />
            </svg>
            <span>{scanning ? t('agents.property-concierge.submit.scanning') : t('agents.property-concierge.submit.upload_photo')}</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => void handleFileSelect(e)}
              disabled={scanning || loading}
              className="hidden"
            />
          </label>

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
          <div className="grid grid-cols-3 gap-2">
            <input
              type="number"
              min={0}
              value={priceMyr}
              onChange={(e) => setPriceMyr(e.target.value)}
              placeholder={t('agents.property-concierge.submit.price_placeholder')}
              className="col-span-2 border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-lime-500/50 dark:border-white/10 dark:placeholder:text-zinc-500"
            />
            <input
              type="number"
              min={0}
              max={50}
              value={bedrooms}
              onChange={(e) => setBedrooms(e.target.value)}
              placeholder="🛏"
              className="border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-lime-500/50 dark:border-white/10 dark:placeholder:text-zinc-500"
            />
          </div>
          <select
            value={propertyType}
            onChange={(e) => setPropertyType(e.target.value)}
            className="border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-lime-500/50 dark:border-white/10 dark:text-zinc-300"
          >
            <option value="">—</option>
            <option value="condo">{t('agents.property-concierge.submit.type.condo')}</option>
            <option value="apartment">{t('agents.property-concierge.submit.type.apartment')}</option>
            <option value="landed">{t('agents.property-concierge.submit.type.landed')}</option>
            <option value="other">{t('agents.property-concierge.submit.type.other')}</option>
          </select>

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
          {status.kind === 'ocr_filled' && (
            <p className="text-xs font-medium text-nk-official-dim dark:text-nk-official">
              {t('agents.property-concierge.submit.ocr_filled')}
            </p>
          )}
          {status.kind === 'ocr_error' && (
            <p className="text-xs font-medium text-red-600 dark:text-red-400">
              {t('agents.property-concierge.submit.ocr_error')}
            </p>
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
