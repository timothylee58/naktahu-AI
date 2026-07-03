'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import useSWR from 'swr';
import type { User } from '@supabase/supabase-js';
import { AuthButton } from '@/components/auth/AuthButton';
import { LangToggle } from '@/components/LangToggle';
import { useI18n } from '@/lib/i18n';

interface HistoryEntry {
  query: string;
  language: string;
  domain: string;
  response_summary: string;
  citations: unknown[];
  ts?: number;
}

export interface AppSidebarProps {
  variant?: 'light' | 'dark';
  isMobileOpen: boolean;
  onMobileClose: () => void;
  showHistory?: boolean;
  user?: User | null;
  accessToken?: string | null;
  onSelectQuery?: (query: string) => void;
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

function truncate(s: string, n = 40) {
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

function HistoryRow({
  entry,
  onClick,
}: {
  entry: HistoryEntry;
  onClick: () => void;
}) {
  const domainClass = DOMAIN_COLORS[entry.domain] ?? DOMAIN_COLORS['general'];
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-2 rounded-lg hover:bg-zinc-100 transition-colors flex flex-col gap-1"
    >
      <span className="text-sm text-zinc-800 leading-snug line-clamp-2">{truncate(entry.query, 56)}</span>
      <span className={`self-start text-[10px] font-semibold px-1.5 py-0.5 rounded locale-nowrap ${domainClass}`}>
        {entry.domain}
      </span>
    </button>
  );
}

function HistoryGroup({
  label,
  entries,
  onSelect,
}: {
  label: string;
  entries: HistoryEntry[];
  onSelect: (q: string) => void;
}) {
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider px-3 locale-nowrap">
        {label}
      </span>
      {entries.map((e, i) => (
        <HistoryRow key={i} entry={e} onClick={() => onSelect(e.query)} />
      ))}
    </div>
  );
}

function SidebarPanel({
  variant,
  showHistory,
  user,
  accessToken,
  onSelectQuery,
  onClose,
  onCollapse,
}: {
  variant: 'light' | 'dark';
  showHistory: boolean;
  user: User | null;
  accessToken: string | null;
  onSelectQuery?: (query: string) => void;
  onClose?: () => void;
  onCollapse?: () => void;
}) {
  const { t } = useI18n();
  const isDark = variant === 'dark';

  const fetcher = useMemo(
    () =>
      accessToken
        ? () =>
            fetch('/api/v1/history', {
              headers: { Authorization: `Bearer ${accessToken}` },
            }).then((r) => {
              if (!r.ok) throw new Error('history fetch failed');
              return r.json() as Promise<HistoryEntry[]>;
            })
        : null,
    [accessToken],
  );

  const { data: entries = [], isLoading: historyLoading, error: historyError, mutate } = useSWR<HistoryEntry[]>(
    showHistory && accessToken ? 'sidebar-history' : null,
    fetcher!,
    { revalidateOnFocus: true },
  );

  const groups = useMemo(() => groupEntries(entries), [entries]);

  const headerBorder = isDark ? 'border-white/10' : 'border-zinc-100';
  const footerBorder = isDark ? 'border-white/10 bg-[#0A0F1E]/80' : 'border-zinc-100 bg-zinc-50/80';
  const titleClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const closeHover = isDark ? 'hover:bg-white/10 text-zinc-400 hover:text-zinc-200' : 'hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700';
  const navLinkClass = isDark
    ? 'text-zinc-300 hover:text-white hover:bg-white/10'
    : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100';
  const dividerClass = isDark ? 'border-white/10' : 'border-zinc-200';

  return (
    <>
      <div className={`flex items-center justify-between px-4 py-3 border-b flex-shrink-0 ${headerBorder}`}>
        <Link href="/" className={`font-bold text-sm tracking-tight locale-nowrap ${titleClass}`}>
          NakTahu
        </Link>
        <div className="flex items-center gap-1 flex-shrink-0">
          {/* collapse — desktop persistent panel only */}
          {onCollapse && (
            <button
              onClick={onCollapse}
              aria-label={t('sidebar.collapse')}
              title={t('sidebar.collapse')}
              className={`hidden lg:inline-flex p-1 rounded ${closeHover}`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                <path fillRule="evenodd" d="M4.25 3A2.25 2.25 0 0 0 2 5.25v9.5A2.25 2.25 0 0 0 4.25 17h11.5A2.25 2.25 0 0 0 18 14.75v-9.5A2.25 2.25 0 0 0 15.75 3H4.25ZM8 4.5v11H4.25a.75.75 0 0 1-.75-.75v-9.5a.75.75 0 0 1 .75-.75H8Zm1.5 0h6.25a.75.75 0 0 1 .75.75v9.5a.75.75 0 0 1-.75.75H9.5v-11Z" clipRule="evenodd" />
              </svg>
            </button>
          )}
          {/* close — mobile overlay only */}
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close sidebar"
              className={`p-1 rounded lg:hidden ${closeHover}`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {showHistory && (
        <div className="flex-1 overflow-y-auto px-2 py-3 flex flex-col gap-4 min-h-0">
          <p className={`text-xs font-semibold uppercase tracking-wider px-3 locale-nowrap ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
            {t('history.title')}
          </p>
          {!user ? (
            <p className={`text-sm text-center px-4 py-6 locale-text-balance ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>
              {t('history.sign_in_prompt')}
            </p>
          ) : historyLoading ? (
            <div className="flex flex-col gap-2 px-2 py-3">
              {[1, 2, 3].map((n) => (
                <div key={n} className={`h-12 rounded-lg animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
              ))}
            </div>
          ) : historyError ? (
            <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
              <p className={`text-sm locale-text-balance ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{t('error.history_fetch')}</p>
              <button
                onClick={() => mutate()}
                className="text-xs font-medium text-blue-600 hover:text-blue-500 transition-colors locale-nowrap"
              >
                {t('error.retry')}
              </button>
            </div>
          ) : entries.length === 0 ? (
            <p className={`text-sm text-center px-4 py-6 locale-text-balance ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
              {t('history.empty')}
            </p>
          ) : (
            <>
              <HistoryGroup
                label={t('history.group.today')}
                entries={groups.today}
                onSelect={(q) => { onSelectQuery?.(q); onClose?.(); }}
              />
              <HistoryGroup
                label={t('history.group.yesterday')}
                entries={groups.yesterday}
                onSelect={(q) => { onSelectQuery?.(q); onClose?.(); }}
              />
              <HistoryGroup
                label={t('history.group.earlier')}
                entries={groups.earlier}
                onSelect={(q) => { onSelectQuery?.(q); onClose?.(); }}
              />
            </>
          )}
        </div>
      )}

      {!showHistory && (
        <nav className="flex flex-col gap-1 px-3 py-4">
          <Link
            href="/chat"
            onClick={onClose}
            className={`flex items-center gap-2 px-3 py-2.5 rounded-lg font-medium text-sm border transition-colors locale-nowrap ${
              isDark
                ? 'border-blue-500/40 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20'
                : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100'
            }`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path fillRule="evenodd" d="M10 2a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 2ZM5.05 4.05a.75.75 0 0 1 1.06 0l1.062 1.06a.75.75 0 1 1-1.061 1.062L5.05 5.111a.75.75 0 0 1 0-1.06Zm9.9 0a.75.75 0 0 1 0 1.061l-1.06 1.061a.75.75 0 0 1-1.062-1.06l1.061-1.062a.75.75 0 0 1 1.061 0ZM3 8a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5A.75.75 0 0 1 3 8Zm11 0a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5A.75.75 0 0 1 14 8Zm-6.828 2.828a3 3 0 1 0 5.656 0 3 3 0 0 0-5.656 0ZM14 16a.75.75 0 0 1-.75.75h-6.5a.75.75 0 0 1 0-1.5h6.5A.75.75 0 0 1 14 16Zm-2.5-3.5a.75.75 0 0 0-3 0V14a.75.75 0 0 0 3 0v-1.5Z" clipRule="evenodd" />
            </svg>
            {t('nav.try_question')}
          </Link>

          <div className={`my-2 border-t ${dividerClass}`} />

          <Link
            href="/"
            onClick={onClose}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors locale-nowrap ${navLinkClass}`}
          >
            {t('nav.home')}
          </Link>
          <Link
            href="/about"
            onClick={onClose}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors locale-nowrap ${navLinkClass}`}
          >
            {t('nav.about')}
          </Link>
          <Link
            href="/faq"
            onClick={onClose}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors locale-nowrap ${navLinkClass}`}
          >
            {t('nav.faq')}
          </Link>
          <Link
            href="/pricing"
            onClick={onClose}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors locale-nowrap ${navLinkClass}`}
          >
            {t('nav.pricing')}
          </Link>

          <div className={`my-2 border-t ${dividerClass}`} />
        </nav>
      )}

      <div className={`flex-shrink-0 border-t px-4 py-4 flex flex-col gap-3 ${footerBorder}`}>
        <LangToggle variant={variant} layout="sidebar" />
        <AuthButton variant={variant} layout="sidebar" />
      </div>
    </>
  );
}

const COLLAPSE_KEY = 'naktahu_sidebar_collapsed';

export function AppSidebar({
  variant = 'light',
  isMobileOpen,
  onMobileClose,
  showHistory = false,
  user = null,
  accessToken = null,
  onSelectQuery,
}: AppSidebarProps) {
  const { t } = useI18n();
  const isDark = variant === 'dark';
  const shellClass = isDark
    ? 'bg-[#0A0F1E] border-white/10 text-white'
    : 'bg-white border-zinc-200 text-zinc-900';

  // Desktop-only collapse of the persistent panel; persisted across reloads.
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    if (localStorage.getItem(COLLAPSE_KEY) === '1') setCollapsed(true);
  }, []);
  const toggleCollapsed = useCallback(() => {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0');
      return next;
    });
  }, []);

  const expandTabClass = isDark
    ? 'bg-[#0A0F1E] border-white/10 text-zinc-300 hover:text-white hover:bg-white/10'
    : 'bg-white border-zinc-200 text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100';

  const panelProps = {
    variant,
    showHistory,
    user,
    accessToken,
    onSelectQuery,
  };

  return (
    <>
      {/* Persistent panel — desktop (hidden when collapsed) */}
      <aside
        className={`${collapsed ? 'hidden' : 'hidden lg:flex'} w-72 flex-shrink-0 flex-col border-r h-full ${shellClass}`}
      >
        <SidebarPanel {...panelProps} onCollapse={toggleCollapsed} />
      </aside>

      {/* Expand tab — desktop only, shown when the panel is collapsed */}
      {collapsed && (
        <button
          onClick={toggleCollapsed}
          aria-label={t('sidebar.expand')}
          title={t('sidebar.expand')}
          className={`hidden lg:flex fixed left-0 top-1/2 -translate-y-1/2 z-40 items-center justify-center w-6 h-16 rounded-r-xl border border-l-0 shadow-md transition-colors ${expandTabClass}`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 0 1 .02-1.06L11.168 10 7.23 6.29a.75.75 0 1 1 1.04-1.08l4.5 4.25a.75.75 0 0 1 0 1.08l-4.5 4.25a.75.75 0 0 1-1.06-.02Z" clipRule="evenodd" />
          </svg>
        </button>
      )}

      <AnimatePresence>
        {isMobileOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/30 z-40 lg:hidden"
              onClick={onMobileClose}
            />
            <motion.aside
              key="sidebar"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 32 }}
              className={`fixed top-0 left-0 h-full w-72 z-50 flex flex-col shadow-xl border-r lg:hidden ${shellClass}`}
            >
              <SidebarPanel {...panelProps} onClose={onMobileClose} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}

/** @deprecated Use AppSidebar */
export const HistorySidebar = AppSidebar;
