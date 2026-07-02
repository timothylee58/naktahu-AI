'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import useSWR from 'swr';
import type { User } from '@supabase/supabase-js';
import { useI18n } from '@/lib/i18n';
import { AuthButton } from '@/components/auth/AuthButton';
import { LangToggle } from '@/components/LangToggle';

interface HistoryEntry {
  query: string;
  language: string;
  domain: string;
  response_summary: string;
  citations: unknown[];
  ts?: number;
}

interface ChatSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  accessToken: string | null;
  onSelectQuery: (query: string) => void;
  onNewChat: () => void;
}

const DAY_MS = 86_400_000;

function groupEntries(entries: HistoryEntry[]) {
  const today: HistoryEntry[] = [];
  const yesterday: HistoryEntry[] = [];
  const earlier: HistoryEntry[] = [];
  const now = Date.now();

  for (const e of entries) {
    if (!e.ts) {
      earlier.push(e);
      continue;
    }
    const diff = now - e.ts * 1000;
    if (diff < DAY_MS) today.push(e);
    else if (diff < DAY_MS * 2) yesterday.push(e);
    else earlier.push(e);
  }
  return { today, yesterday, earlier };
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

function HistoryRow({ entry, onClick }: { entry: HistoryEntry; onClick: () => void }) {
  const domainClass = DOMAIN_COLORS[entry.domain] ?? DOMAIN_COLORS['general'];
  return (
    <button
      onClick={onClick}
      title={entry.query}
      className="w-full text-left px-3 py-2 rounded-lg hover:bg-zinc-100 transition-colors flex flex-col gap-1"
    >
      {/* line-clamp keeps long BM/EN/ZH queries to two tidy lines instead of overflowing */}
      <span className="text-sm text-zinc-800 leading-snug line-clamp-2 break-words">
        {entry.query}
      </span>
      <span
        className={`self-start text-[10px] font-semibold px-1.5 py-0.5 rounded ${domainClass}`}
      >
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
      <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider px-3">
        {label}
      </span>
      {entries.map((e, i) => (
        <HistoryRow key={i} entry={e} onClick={() => onSelect(e.query)} />
      ))}
    </div>
  );
}

function SidebarInner({
  user,
  accessToken,
  onSelectQuery,
  onNewChat,
  onClose,
}: Omit<ChatSidebarProps, 'isOpen'>) {
  const { t } = useI18n();

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

  const {
    data: entries = [],
    isLoading: historyLoading,
    error: historyError,
    mutate,
  } = useSWR<HistoryEntry[]>(accessToken ? 'history' : null, fetcher!, {
    revalidateOnFocus: true,
  });

  const groups = useMemo(() => groupEntries(entries), [entries]);

  return (
    <div className="flex h-full flex-col">
      {/* brand */}
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-zinc-100">
        <Link href="/" className="flex flex-col min-w-0">
          <span className="text-base font-bold text-zinc-900 tracking-tight">
            {t('header.title')}
          </span>
          <span className="text-[11px] text-zinc-500 truncate">
            {t('header.subtitle')}
          </span>
        </Link>
        {/* close — mobile overlay only */}
        <button
          onClick={onClose}
          aria-label={t('auth.error.dismiss')}
          className="md:hidden p-1 rounded hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700 flex-shrink-0"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
          </svg>
        </button>
      </div>

      {/* new chat */}
      <div className="px-3 pt-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 flex-shrink-0">
            <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
          </svg>
          <span className="truncate">{t('chat.new_chat')}</span>
        </button>
      </div>

      {/* history */}
      <div className="flex-1 min-h-0 overflow-y-auto px-2 py-3 flex flex-col gap-3">
        <span className="px-3 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
          {t('history.title')}
        </span>
        {!user ? (
          <p className="text-sm text-zinc-500 text-center px-4 py-8 leading-relaxed">
            {t('history.sign_in_prompt')}
          </p>
        ) : historyLoading ? (
          <div className="flex flex-col gap-2 px-1">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-12 rounded-lg bg-zinc-100 animate-pulse" />
            ))}
          </div>
        ) : historyError ? (
          <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
            <p className="text-sm text-zinc-500">{t('error.history_fetch')}</p>
            <button
              onClick={() => mutate()}
              className="text-xs font-medium text-blue-600 hover:text-blue-500 transition-colors"
            >
              {t('error.retry')}
            </button>
          </div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-zinc-400 text-center px-4 py-8">
            {t('history.empty')}
          </p>
        ) : (
          <>
            <HistoryGroup label={t('history.group.today')} entries={groups.today} onSelect={onSelectQuery} />
            <HistoryGroup label={t('history.group.yesterday')} entries={groups.yesterday} onSelect={onSelectQuery} />
            <HistoryGroup label={t('history.group.earlier')} entries={groups.earlier} onSelect={onSelectQuery} />
          </>
        )}
      </div>

      {/* footer: language + auth */}
      <div className="border-t border-zinc-100 px-3 py-3 flex items-center justify-between gap-2">
        <LangToggle variant="light" />
        <AuthButton variant="light" />
      </div>
    </div>
  );
}

export function ChatSidebar({
  isOpen,
  onClose,
  user,
  accessToken,
  onSelectQuery,
  onNewChat,
}: ChatSidebarProps) {
  const inner = (
    <SidebarInner
      user={user}
      accessToken={accessToken}
      onSelectQuery={onSelectQuery}
      onNewChat={onNewChat}
      onClose={onClose}
    />
  );

  return (
    <>
      {/* Persistent panel — desktop */}
      <aside className="hidden md:flex md:flex-col md:w-72 md:flex-shrink-0 border-r border-zinc-200 bg-white">
        {inner}
      </aside>

      {/* Slide-over panel — mobile */}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/30 z-20 md:hidden"
              onClick={onClose}
            />
            <motion.aside
              key="sidebar"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 320, damping: 32 }}
              className="fixed top-0 left-0 h-full w-72 max-w-[85vw] bg-white border-r border-zinc-200 z-30 shadow-xl md:hidden"
            >
              {inner}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
