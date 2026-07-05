'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import useSWR from 'swr';
import type { User } from '@supabase/supabase-js';
import { AuthButton } from '@/components/auth/AuthButton';
import { DeadlineWidget } from '@/components/agents/DeadlineWidget';
import { SidebarAgentsNav } from '@/components/agents/SidebarAgentsNav';
import { LangToggle } from '@/components/LangToggle';
import { ThemeToggle } from '@/components/ThemeToggle';
import { SiteNavLinks } from '@/components/layout/SiteNavLinks';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';
import { fetchHistoryAuthed, HistoryFetchError, HISTORY_SWR_OPTIONS, type HistoryEntry } from '@/lib/history';
import { canAccessHistory } from '@/lib/auth-plan';

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
  tax: 'bg-orange-500/20 text-orange-300',
  epf: 'bg-green-500/20 text-green-300',
  business: 'bg-purple-500/20 text-purple-300',
  education: 'bg-blue-500/20 text-blue-300',
  health: 'bg-red-500/20 text-red-300',
  immigration: 'bg-teal-500/20 text-teal-300',
  general: 'bg-white/10 text-zinc-300',
};

function HistoryRow({
  entry,
  onClick,
  isDark,
}: {
  entry: HistoryEntry;
  onClick: () => void;
  isDark: boolean;
}) {
  const colors = isDark ? DOMAIN_COLORS_DARK : DOMAIN_COLORS_LIGHT;
  const domainClass = colors[entry.domain] ?? colors['general'];
  const hoverClass = isDark ? 'hover:bg-white/10' : 'hover:bg-zinc-100';
  const textClass = isDark ? 'text-zinc-200' : 'text-zinc-800';

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-lg transition-colors flex flex-col gap-1 ${hoverClass}`}
    >
      <span className={`text-sm leading-snug line-clamp-2 ${textClass}`}>{truncate(entry.query, 56)}</span>
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
  isDark,
}: {
  label: string;
  entries: HistoryEntry[];
  onSelect: (q: string) => void;
  isDark: boolean;
}) {
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className={`text-[11px] font-semibold uppercase tracking-wider px-3 locale-nowrap ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
        {label}
      </span>
      {entries.map((e, i) => (
        <HistoryRow key={i} entry={e} onClick={() => onSelect(e.query)} isDark={isDark} />
      ))}
    </div>
  );
}

function SidebarPanel({
  variant,
  showHistory,
  user,
  onSelectQuery,
  onClose,
}: {
  variant: 'light' | 'dark';
  showHistory: boolean;
  user: User | null;
  accessToken?: string | null;
  onSelectQuery?: (query: string) => void;
  onClose?: () => void;
}) {
  const { t } = useI18n();
  const isDark = variant === 'dark';
  const supabase = useMemo(() => createClient(), []);

  const historyEnabled = Boolean(showHistory && user && canAccessHistory(user));

  const { data: entries = [], isLoading: historyLoading, error: historyError, mutate } = useSWR<HistoryEntry[]>(
    historyEnabled && user ? ['sidebar-history', user.id] : null,
    () => fetchHistoryAuthed(supabase),
    HISTORY_SWR_OPTIONS,
  );

  const groups = useMemo(() => groupEntries(entries), [entries]);

  const headerBorder = isDark ? 'border-white/10' : 'border-zinc-100';
  const footerBorder = isDark ? 'border-white/10 bg-[#0A0F1E]/80' : 'border-zinc-100 bg-zinc-50/80';
  const titleClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const closeHover = isDark ? 'hover:bg-white/10 text-zinc-400 hover:text-zinc-200' : 'hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700';
  const dividerClass = isDark ? 'border-white/10' : 'border-zinc-200';
  const mutedText = isDark ? 'text-zinc-400' : 'text-zinc-500';

  return (
    <>
      <div className={`flex items-center justify-between px-4 py-3 border-b flex-shrink-0 ${headerBorder}`}>
        <Link href="/chat" className={`font-bold text-sm tracking-tight locale-nowrap ${titleClass}`}>
          NakTahu
        </Link>
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

      <div className={`flex-shrink-0 px-2 py-3 border-b ${headerBorder}`}>
        <SiteNavLinks
          variant={variant}
          layout="vertical"
          onNavigate={onClose}
        />
      </div>

      {showHistory && (
        <div className="flex-1 overflow-y-auto px-2 py-3 flex flex-col gap-4 min-h-0">
          <DeadlineWidget userId={user?.id ?? null} variant={variant} />
          <SidebarAgentsNav
            user={user}
            isDark={isDark}
            navLinkClass={isDark ? 'text-zinc-300 hover:text-white hover:bg-white/10' : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'}
            dividerClass={dividerClass}
            onClose={onClose}
            compact
          />
          <p className={`text-xs font-semibold uppercase tracking-wider px-3 locale-nowrap ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
            {t('history.title')}
          </p>
          {!user ? (
            <p className={`text-sm text-center px-4 py-6 locale-text-balance ${mutedText}`}>
              {t('history.sign_in_prompt')}
            </p>
          ) : !canAccessHistory(user) ? (
            <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
              <p className={`text-sm locale-text-balance ${mutedText}`}>
                {t('error.history_pro_required')}
              </p>
              <Link
                href="/pricing"
                className="text-xs font-medium text-blue-600 hover:text-blue-500 transition-colors locale-nowrap"
              >
                {t('nav.pricing')}
              </Link>
            </div>
          ) : historyLoading ? (
            <div className="flex flex-col gap-2 px-2 py-3">
              {[1, 2, 3].map((n) => (
                <div key={n} className={`h-12 rounded-lg animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
              ))}
            </div>
          ) : historyError ? (
            <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
              <p className={`text-sm locale-text-balance ${mutedText}`}>
                {historyError instanceof HistoryFetchError && historyError.code === 'pro_required'
                  ? t('error.history_pro_required')
                  : t('error.history_fetch')}
              </p>
              {historyError instanceof HistoryFetchError && historyError.code === 'pro_required' ? (
                <Link
                  href="/pricing"
                  className="text-xs font-medium text-blue-600 hover:text-blue-500 transition-colors locale-nowrap"
                >
                  {t('nav.pricing')}
                </Link>
              ) : (
                <button
                  onClick={() => mutate()}
                  className="text-xs font-medium text-blue-600 hover:text-blue-500 transition-colors locale-nowrap"
                >
                  {t('error.retry')}
                </button>
              )}
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
                isDark={isDark}
              />
              <HistoryGroup
                label={t('history.group.yesterday')}
                entries={groups.yesterday}
                onSelect={(q) => { onSelectQuery?.(q); onClose?.(); }}
                isDark={isDark}
              />
              <HistoryGroup
                label={t('history.group.earlier')}
                entries={groups.earlier}
                onSelect={(q) => { onSelectQuery?.(q); onClose?.(); }}
                isDark={isDark}
              />
            </>
          )}
        </div>
      )}

      {!showHistory && (
        <div className="flex-1 min-h-0" />
      )}

      <div className={`flex-shrink-0 border-t px-4 py-4 flex flex-col gap-3 ${footerBorder}`}>
        <ThemeToggle variant={variant} layout="sidebar" />
        <LangToggle variant={variant} layout="sidebar" />
        <AuthButton variant={variant} layout="sidebar" />
      </div>
    </>
  );
}

export function AppSidebar({
  variant = 'light',
  isMobileOpen,
  onMobileClose,
  showHistory = false,
  user = null,
  accessToken = null,
  onSelectQuery,
}: AppSidebarProps) {
  const isDark = variant === 'dark';
  const shellClass = isDark
    ? 'bg-[#0A0F1E] border-white/10 text-white'
    : 'bg-white border-zinc-200 text-zinc-900';

  const panelProps = {
    variant,
    showHistory,
    user,
    accessToken,
    onSelectQuery,
  };

  return (
    <>
      <aside
        className={`hidden lg:flex w-72 flex-shrink-0 flex-col border-r h-full ${shellClass}`}
      >
        <SidebarPanel {...panelProps} />
      </aside>

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
