'use client';

import { useCallback, useEffect, useState } from 'react';
import { useI18n } from '@/lib/i18n';
import { createClient } from '@/lib/supabase/client';
import { fetchWithAuth } from '@/lib/auth-headers';
import { API_BASE } from '@/lib/api-base';

type Provider = 'google' | 'microsoft';

interface ConnectionStatus {
  provider: Provider;
  connected: boolean;
  last_synced_at: string | null;
  last_error: string | null;
}

const PROVIDERS: { id: Provider; labelKey: string }[] = [
  { id: 'google', labelKey: 'calendar.google' },
  { id: 'microsoft', labelKey: 'calendar.microsoft' },
];

/** Provider marks drawn as inline SVG rather than pulled from a CDN — the
 * app self-hosts every asset, and these two are simple enough to author
 * exactly. Google's four-colour G and Microsoft's four-square logo are
 * each rendered in their official brand colours (both companies' brand
 * guidelines require the mark be shown unmodified in a "sign in with"
 * context, so these are NOT recoloured to match NakTahu's palette). */
function ProviderMark({ provider }: { provider: Provider }) {
  if (provider === 'google') {
    return (
      <svg viewBox="0 0 24 24" className="w-7 h-7" aria-hidden>
        <path fill="#4285F4" d="M23.06 12.25c0-.86-.08-1.68-.22-2.47H12v4.68h6.2a5.3 5.3 0 0 1-2.3 3.48v2.9h3.72c2.18-2 3.44-4.96 3.44-8.59Z" />
        <path fill="#34A853" d="M12 23.5c3.11 0 5.72-1.03 7.62-2.79l-3.72-2.89c-1.03.69-2.35 1.1-3.9 1.1-3 0-5.54-2.03-6.45-4.75H1.7v2.98A11.5 11.5 0 0 0 12 23.5Z" />
        <path fill="#FBBC05" d="M5.55 14.17a6.9 6.9 0 0 1 0-4.34V6.85H1.7a11.51 11.51 0 0 0 0 10.3l3.85-2.98Z" />
        <path fill="#EA4335" d="M12 4.92c1.69 0 3.21.58 4.4 1.72l3.3-3.3C17.71 1.44 15.1.5 12 .5A11.5 11.5 0 0 0 1.7 6.85l3.85 2.98C6.46 7.11 9 4.92 12 4.92Z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className="w-7 h-7" aria-hidden>
      <path fill="#F25022" d="M2 2h9.5v9.5H2z" />
      <path fill="#7FBA00" d="M12.5 2H22v9.5h-9.5z" />
      <path fill="#00A4EF" d="M2 12.5h9.5V22H2z" />
      <path fill="#FFB900" d="M12.5 12.5H22V22h-9.5z" />
    </svg>
  );
}

export function CalendarConnectCards() {
  const { t, locale } = useI18n();
  const [statuses, setStatuses] = useState<ConnectionStatus[] | null>(null);
  const [busy, setBusy] = useState<Provider | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const supabase = createClient();
      const res = await fetchWithAuth(supabase, `${API_BASE}/api/v1/calendar/status`);
      if (!res.ok) throw new Error('unavailable');
      setStatuses((await res.json()) as ConnectionStatus[]);
    } catch {
      setStatuses([]);
      setError('unavailable');
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  // The OAuth callback redirects back here with ?calendar_connected= or
  // ?calendar_error=. Read it once, surface it, then strip the param so a
  // refresh doesn't replay a stale banner.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('calendar_error')) setError('connect');
    if (params.get('calendar_connected')) void loadStatus();
    if (params.has('calendar_error') || params.has('calendar_connected')) {
      params.delete('calendar_error');
      params.delete('calendar_connected');
      const qs = params.toString();
      window.history.replaceState({}, '', qs ? `${window.location.pathname}?${qs}` : window.location.pathname);
    }
  }, [loadStatus]);

  const handleConnect = useCallback(async (provider: Provider) => {
    setBusy(provider);
    setError(null);
    try {
      const supabase = createClient();
      const res = await fetchWithAuth(supabase, `${API_BASE}/api/v1/calendar/connect/${provider}`);
      if (!res.ok) throw new Error('unavailable');
      const { authorize_url: authorizeUrl } = (await res.json()) as { authorize_url: string };
      window.location.href = authorizeUrl;
    } catch {
      setError('unavailable');
      setBusy(null);
    }
  }, []);

  const handleDisconnect = useCallback(async (provider: Provider) => {
    setBusy(provider);
    setError(null);
    try {
      const supabase = createClient();
      const res = await fetchWithAuth(supabase, `${API_BASE}/api/v1/calendar/${provider}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('unavailable');
      await loadStatus();
    } catch {
      setError('unavailable');
    } finally {
      setBusy(null);
    }
  }, [loadStatus]);

  const statusFor = (provider: Provider) => statuses?.find((s) => s.provider === provider);

  return (
    <section className="flex flex-col gap-3 rounded-2xl border border-zinc-200 bg-white px-4 py-4 dark:border-white/10 dark:bg-white/5">
      <div className="flex flex-col gap-1">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{t('calendar.title')}</h2>
        <p className="text-xs leading-relaxed text-zinc-500 dark:text-zinc-400 locale-text-balance">
          {t('calendar.desc')}
        </p>
      </div>

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-1.5 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
          {error === 'connect' ? t('calendar.error.connect') : t('calendar.unavailable')}
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {PROVIDERS.map(({ id, labelKey }) => {
          const status = statusFor(id);
          const connected = status?.connected ?? false;
          return (
            <div
              key={id}
              className="flex flex-col items-center gap-2 rounded-xl border border-zinc-200 px-4 py-4 dark:border-white/10"
            >
              <ProviderMark provider={id} />
              <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300 locale-nowrap">{t(labelKey)}</span>

              {connected ? (
                <>
                  <span className="text-[10px] text-zinc-500 dark:text-zinc-400 text-center">
                    {status?.last_error
                      ? t('calendar.error.reconnect')
                      : status?.last_synced_at
                        ? `${t('calendar.last_synced')}: ${new Date(status.last_synced_at).toLocaleDateString(
                            locale === 'zh' ? 'zh-CN' : locale === 'ms' ? 'ms-MY' : 'en-MY',
                          )}`
                        : t('calendar.never_synced')}
                  </span>
                  <button
                    type="button"
                    onClick={() => void handleDisconnect(id)}
                    disabled={busy === id}
                    className="text-xs font-semibold text-zinc-600 hover:text-red-600 disabled:opacity-40 transition-colors dark:text-zinc-400 dark:hover:text-red-400"
                  >
                    {t('calendar.disconnect')}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => void handleConnect(id)}
                  disabled={busy === id || statuses === null}
                  className="rounded-full bg-nk-official px-4 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-nk-official-dim disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {t('calendar.connect')}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
