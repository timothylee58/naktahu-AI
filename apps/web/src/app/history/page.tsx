'use client';

export const dynamic = 'force-dynamic';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import { useI18n } from '@/lib/i18n';
import {
  fetchHistoryAuthed,
  HistoryFetchError,
  HISTORY_SWR_OPTIONS,
  historyPageKey,
  HISTORY_RESTORE_STORAGE_KEY,
  type HistoryEntry,
} from '@/lib/history';
import { canAccessHistory } from '@/lib/auth-plan';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { useTheme } from '@/lib/theme';
import { AgentRunHistorySection } from '@/components/history/AgentRunHistorySection';

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

const DOMAIN_COLORS_LIGHT: Record<string, string> = {
  tax: 'bg-orange-100 text-orange-700',
  epf: 'bg-green-100 text-green-700',
  business: 'bg-purple-100 text-purple-700',
  education: 'bg-blue-100 text-blue-700',
  health: 'bg-red-100 text-red-700',
  immigration: 'bg-teal-100 text-teal-700',
  general: 'bg-zinc-100 text-zinc-600',
};

const DOMAIN_COLORS_DARK: Record<string, string> = {
  tax: 'bg-orange-500/15 text-orange-300',
  epf: 'bg-green-500/15 text-green-300',
  business: 'bg-purple-500/15 text-purple-300',
  education: 'bg-blue-500/15 text-blue-300',
  health: 'bg-red-500/15 text-red-300',
  immigration: 'bg-teal-500/15 text-teal-300',
  general: 'bg-white/10 text-zinc-300',
};

function HistorySection({
  label,
  entries,
  isDark,
  onSelect,
}: {
  label: string;
  entries: HistoryEntry[];
  isDark: boolean;
  onSelect: (entry: HistoryEntry) => void;
}) {
  if (entries.length === 0) return null;
  const domainColors = isDark ? DOMAIN_COLORS_DARK : DOMAIN_COLORS_LIGHT;
  return (
    <section className="flex flex-col gap-2">
      <h2 className={`text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
        {label}
      </h2>
      <ul className="flex flex-col gap-1">
        {entries.map((e, i) => {
          const domainClass = domainColors[e.domain] ?? domainColors['general'];
          return (
            <li key={i}>
              <button
                type="button"
                onClick={() => onSelect(e)}
                className={`w-full text-left rounded-xl px-4 py-3 flex flex-col gap-1.5 shadow-sm border transition-colors ${
                  isDark
                    ? 'bg-white/5 border-white/10 hover:bg-white/10'
                    : 'bg-white border-zinc-100 hover:bg-zinc-50'
                }`}
              >
                <span
                  title={e.response_summary?.trim() || e.query}
                  className={`text-sm font-medium leading-snug line-clamp-2 ${isDark ? 'text-zinc-200' : 'text-zinc-800'}`}
                >
                  {truncate(e.response_summary?.trim() || e.query, 80)}
                </span>
                {e.response_summary?.trim() && (
                  <span title={e.query} className={`text-xs line-clamp-1 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                    {truncate(e.query, 56)}
                  </span>
                )}
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${domainClass}`}>
                    {e.domain}
                  </span>
                </div>
              </button>
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
  const router = useRouter();
  const { supabase, user, userId, accessToken, ready } = useSupabaseSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const handleSelectEntry = (entry: HistoryEntry) => {
    if (entry.response_text) {
      sessionStorage.setItem(HISTORY_RESTORE_STORAGE_KEY, JSON.stringify(entry));
      router.push('/chat');
    } else {
      // Pre-migration-028 rows have no stored response_text — fall back to
      // the old re-prompt behavior since there's nothing to show back.
      router.push(`/chat?q=${encodeURIComponent(entry.query)}`);
    }
  };

  const historyEnabled = Boolean(userId && user && canAccessHistory(user));

  const { data: entries = [], isLoading: historyLoading, error: historyError, mutate } = useSWR<HistoryEntry[]>(
    historyEnabled && userId ? historyPageKey(userId) : null,
    () => fetchHistoryAuthed(supabase),
    HISTORY_SWR_OPTIONS,
  );

  const groups = useMemo(() => groupEntries(entries), [entries]);

  return (
    <div className={`flex h-full ${isDark ? 'bg-[#12151C]' : 'bg-zinc-50/50'}`}>
      <AppSidebar
        variant={isDark ? 'dark' : 'light'}
        isMobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        showHistory
        user={user}
        accessToken={accessToken}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
      />

      <div className="flex flex-col flex-1 min-w-0 h-full overflow-y-auto">
        <header
          className={`flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b backdrop-blur-md sticky top-0 z-10 shadow-sm ${
            isDark ? 'border-white/10 bg-[#12151C]/90 text-white' : 'border-zinc-100 bg-white/90 text-zinc-900'
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
              <path
                fillRule="evenodd"
                d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          <Link href="/" className="flex flex-col">
            <span className="text-base font-bold tracking-tight">{t('header.title')}</span>
            <span className={`text-xs ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{t('header.subtitle')}</span>
          </Link>
        </header>

        <main className="flex-1 px-4 py-6 max-w-2xl w-full mx-auto flex flex-col gap-6">
          <h1 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-zinc-900'}`}>{t('history.title')}</h1>

          {/* Agent-run history is intentionally NOT behind canAccessHistory's
              pro-gate below — it spans every plan tier (health-triage and
              retrenchment-navigator are free), so a free user must still see
              their own past agent output even while the chat-history section
              beneath shows the pro-upsell state. */}
          {ready && user && userId && (
            <AgentRunHistorySection supabase={supabase} userId={userId} isDark={isDark} />
          )}

          {!ready ? (
            <div className="flex flex-col gap-3">
              {[1, 2, 3].map((n) => (
                <div key={n} className={`h-16 rounded-xl animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
              ))}
            </div>
          ) : !user ? (
            <p className={`text-sm text-center py-12 ${isDark ? 'text-zinc-500' : 'text-zinc-500'}`}>
              {t('history.sign_in_prompt')}
            </p>
          ) : !canAccessHistory(user) ? (
            <div className="flex flex-col items-center gap-4 py-16 text-center">
              <p className={`text-sm ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{t('error.history_pro_required')}</p>
              <Link href="/pricing" className="text-sm font-semibold text-blue-600 hover:text-blue-500 transition-colors">
                {t('nav.pricing')}
              </Link>
            </div>
          ) : historyLoading ? (
            <div className="flex flex-col gap-3">
              {[1, 2, 3, 4].map((n) => (
                <div key={n} className={`h-16 rounded-xl animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
              ))}
            </div>
          ) : historyError ? (
            <div className="flex flex-col items-center gap-4 py-16 text-center">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center ${isDark ? 'bg-red-500/10' : 'bg-red-50'}`}>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-5 h-5 ${isDark ? 'text-red-400' : 'text-red-400'}`}>
                  <path fillRule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
                </svg>
              </div>
              <p className={`text-sm ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
                {historyError instanceof HistoryFetchError && historyError.code === 'pro_required'
                  ? t('error.history_pro_required')
                  : t('error.history_fetch')}
              </p>
              {historyError instanceof HistoryFetchError && historyError.code === 'pro_required' ? (
                <Link href="/pricing" className="text-sm font-semibold text-blue-600 hover:text-blue-500 transition-colors">
                  {t('nav.pricing')}
                </Link>
              ) : (
                <button onClick={() => mutate()} className="text-sm font-semibold text-blue-600 hover:text-blue-500 transition-colors">
                  {t('error.retry')}
                </button>
              )}
            </div>
          ) : entries.length === 0 ? (
            <p className={`text-sm text-center py-12 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>{t('history.empty')}</p>
          ) : (
            <>
              <HistorySection label={t('history.group.today')} entries={groups.today} isDark={isDark} onSelect={handleSelectEntry} />
              <HistorySection label={t('history.group.yesterday')} entries={groups.yesterday} isDark={isDark} onSelect={handleSelectEntry} />
              <HistorySection label={t('history.group.earlier')} entries={groups.earlier} isDark={isDark} onSelect={handleSelectEntry} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}
