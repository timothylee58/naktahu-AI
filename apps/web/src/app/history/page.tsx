'use client';

export const dynamic = 'force-dynamic';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { useI18n } from '@/lib/i18n';
import { fetchHistoryAuthed, HistoryFetchError, HISTORY_SWR_OPTIONS, type HistoryEntry } from '@/lib/history';
import { canAccessHistory } from '@/lib/auth-plan';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { ThemeToggle } from '@/components/ThemeToggle';
import { useTheme } from '@/lib/theme';

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
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const { supabase, user, userId, accessToken, ready } = useSupabaseSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const historyEnabled = Boolean(userId && user && canAccessHistory(user) && ready);

  const { data: entries = [], isLoading: historyLoading, error: historyError, mutate } = useSWR<HistoryEntry[]>(
    historyEnabled ? ['history-page', userId] : null,
    () => fetchHistoryAuthed(supabase),
    HISTORY_SWR_OPTIONS,
  );

  const groups = useMemo(() => groupEntries(entries), [entries]);

  return (
    <div className={`min-h-screen flex ${isDark ? 'bg-[#0A0F1E]' : 'bg-zinc-50'}`}>
      <AppSidebar
        variant={isDark ? 'dark' : 'light'}
        isMobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        showHistory
        user={user}
        accessToken={accessToken}
      />

      <div className="flex flex-col flex-1 min-w-0 min-h-screen">
      <header className={`border-b px-4 py-3 flex items-center justify-between gap-3 ${isDark ? 'bg-[#0A0F1E]/90 border-white/10 text-white' : 'bg-white border-zinc-200 text-zinc-900'}`}>
        <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={() => setSidebarOpen(true)}
          aria-label={t('header.menu')}
          className={`p-1.5 rounded-lg transition-colors lg:hidden ${isDark ? 'text-zinc-400 hover:bg-white/10' : 'text-zinc-500 hover:bg-zinc-100'}`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
          </svg>
        </button>
        <Link href="/chat" className={`p-1 rounded flex-shrink-0 ${isDark ? 'hover:bg-white/10 text-zinc-400' : 'hover:bg-zinc-100 text-zinc-500'}`}>
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
        <h1 className="font-semibold truncate locale-nowrap">{t('history.title')}</h1>
        </div>
        <ThemeToggle variant={isDark ? 'dark' : 'light'} />
      </header>

      {/* Content */}
      <main className="flex-1 px-4 py-6 max-w-2xl w-full mx-auto flex flex-col gap-6">
        {!ready || historyLoading ? (
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
        ) : !canAccessHistory(user) ? (
          <div className="flex flex-col items-center gap-4 py-16 text-center">
            <p className="text-sm text-zinc-500">{t('error.history_pro_required')}</p>
            <Link
              href="/pricing"
              className="text-sm font-semibold text-blue-600 hover:text-blue-500 transition-colors"
            >
              {t('nav.pricing')}
            </Link>
          </div>
        ) : historyLoading ? (
          <div className="flex flex-col gap-3">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className="h-16 rounded-xl bg-white border border-zinc-100 animate-pulse"
              />
            ))}
          </div>
        ) : historyError ? (
          <div className="flex flex-col items-center gap-4 py-16 text-center">
            <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-red-400">
                <path fillRule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
              </svg>
            </div>
            <p className="text-sm text-zinc-500">
              {historyError instanceof HistoryFetchError && historyError.code === 'pro_required'
                ? t('error.history_pro_required')
                : t('error.history_fetch')}
            </p>
            {historyError instanceof HistoryFetchError && historyError.code === 'pro_required' ? (
              <Link
                href="/pricing"
                className="text-sm font-semibold text-blue-600 hover:text-blue-500 transition-colors"
              >
                {t('nav.pricing')}
              </Link>
            ) : (
              <button
                onClick={() => mutate()}
                className="text-sm font-semibold text-blue-600 hover:text-blue-500 transition-colors"
              >
                {t('error.retry')}
              </button>
            )}
          </div>
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
    </div>
  );
}
