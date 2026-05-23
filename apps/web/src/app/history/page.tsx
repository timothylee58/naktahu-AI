'use client';

export const dynamic = 'force-dynamic';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';

interface HistoryEntry {
  query: string;
  language: string;
  domain: string;
  response_summary: string;
  citations: unknown[];
  ts?: number;
}

const DAY_MS = 86_400_000;

function groupEntries(entries: HistoryEntry[]) {
  const today: HistoryEntry[] = [];
  const yesterday: HistoryEntry[] = [];
  const earlier: HistoryEntry[] = [];
  const now = Date.now();

  for (const e of entries) {
    if (!e.ts) { earlier.push(e); continue; }
    const diff = now - e.ts * 1000;
    if (diff < DAY_MS) today.push(e);
    else if (diff < DAY_MS * 2) yesterday.push(e);
    else earlier.push(e);
  }
  return { today, yesterday, earlier };
}

function truncate(s: string, n = 60) {
  return s.length <= n ? s : `${s.slice(0, n)}…`;
}

const DOMAIN_COLORS: Record<string, string> = {
  tax: 'bg-orange-100 text-orange-700',
  epf: 'bg-green-100 text-green-700',
  business: 'bg-purple-100 text-purple-700',
  education: 'bg-blue-100 text-blue-700',
  health: 'bg-red-100 text-red-700',
  immigration: 'bg-teal-100 text-teal-700',
  general: 'bg-zinc-100 text-zinc-600',
};

function HistorySection({
  label,
  entries,
}: {
  label: string;
  entries: HistoryEntry[];
}) {
  if (entries.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
        {label}
      </h2>
      <ul className="flex flex-col gap-1">
        {entries.map((e, i) => {
          const domainClass =
            DOMAIN_COLORS[e.domain] ?? DOMAIN_COLORS['general'];
          return (
            <li
              key={i}
              className="bg-white border border-zinc-100 rounded-xl px-4 py-3 flex flex-col gap-1.5 shadow-sm"
            >
              <span className="text-sm font-medium text-zinc-800 leading-snug">
                {truncate(e.query)}
              </span>
              <div className="flex items-center gap-2">
                <span
                  className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${domainClass}`}
                >
                  {e.domain}
                </span>
                {e.response_summary && (
                  <span className="text-xs text-zinc-400 truncate">
                    {truncate(e.response_summary, 60)}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default function HistoryPage() {
  const { t } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setAccessToken(data.session?.access_token ?? null);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setAccessToken(session?.access_token ?? null);
    });

    return () => subscription.unsubscribe();
  }, [supabase]);

  const fetcher = useMemo(
    () =>
      accessToken
        ? () =>
            fetch('/api/v1/history', {
              headers: { Authorization: `Bearer ${accessToken}` },
            }).then((r) => r.json() as Promise<HistoryEntry[]>)
        : null,
    [accessToken],
  );

  const { data: entries = [] } = useSWR<HistoryEntry[]>(
    accessToken ? 'history-page' : null,
    fetcher!,
    { revalidateOnFocus: true },
  );

  const groups = useMemo(() => groupEntries(entries), [entries]);

  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-zinc-200 px-4 py-3 flex items-center gap-3">
        <Link href="/chat" className="p-1 rounded hover:bg-zinc-100 text-zinc-500">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5"
          >
            <path
              fillRule="evenodd"
              d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 1 1 1.04 1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10Z"
              clipRule="evenodd"
            />
          </svg>
        </Link>
        <h1 className="font-semibold text-zinc-900">{t('history.title')}</h1>
      </header>

      {/* Content */}
      <main className="flex-1 px-4 py-6 max-w-2xl w-full mx-auto flex flex-col gap-6">
        {loading ? (
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="h-16 rounded-xl bg-white border border-zinc-100 animate-pulse"
              />
            ))}
          </div>
        ) : !user ? (
          <p className="text-sm text-zinc-500 text-center py-12">
            {t('history.sign_in_prompt')}
          </p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-zinc-400 text-center py-12">
            {t('history.empty')}
          </p>
        ) : (
          <>
            <HistorySection
              label={t('history.group.today')}
              entries={groups.today}
            />
            <HistorySection
              label={t('history.group.yesterday')}
              entries={groups.yesterday}
            />
            <HistorySection
              label={t('history.group.earlier')}
              entries={groups.earlier}
            />
          </>
        )}
      </main>
    </div>
  );
}
