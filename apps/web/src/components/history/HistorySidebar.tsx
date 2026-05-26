'use client';

import { useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import useSWR from 'swr';
import type { User } from '@supabase/supabase-js';
import { useI18n } from '@/lib/i18n';

interface HistoryEntry {
  query: string;
  language: string;
  domain: string;
  response_summary: string;
  citations: unknown[];
  ts?: number;
}

interface HistorySidebarProps {
  isOpen: boolean;
  onClose: () => void;
  user: User | null;
  accessToken: string | null;
  onSelectQuery: (query: string) => void;
}

const NOW = Date.now();
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
  const domainClass =
    DOMAIN_COLORS[entry.domain] ?? DOMAIN_COLORS['general'];
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-2 rounded-lg hover:bg-zinc-100 transition-colors flex flex-col gap-1"
    >
      <span className="text-sm text-zinc-800 leading-snug">
        {truncate(entry.query)}
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

void NOW; // suppress lint

export function HistorySidebar({
  isOpen,
  onClose,
  user,
  accessToken,
  onSelectQuery,
}: HistorySidebarProps) {
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

  const { data: entries = [] } = useSWR<HistoryEntry[]>(
    accessToken ? 'history' : null,
    fetcher!,
    { revalidateOnFocus: true },
  );

  const groups = useMemo(() => groupEntries(entries), [entries]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/30 z-20 sm:hidden"
            onClick={onClose}
          />

          {/* sidebar panel */}
          <motion.aside
            key="sidebar"
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            className="fixed top-0 left-0 h-full w-72 bg-white border-r border-zinc-200 z-30 flex flex-col shadow-xl"
          >
            {/* header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100">
              <span className="font-semibold text-zinc-900 text-sm">
                {t('history.title')}
              </span>
              <button
                onClick={onClose}
                aria-label="Close sidebar"
                className="p-1 rounded hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="w-5 h-5"
                >
                  <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                </svg>
              </button>
            </div>

            {/* body */}
            <div className="flex-1 overflow-y-auto px-2 py-3 flex flex-col gap-4">
              {!user ? (
                <p className="text-sm text-zinc-500 text-center px-4 py-8">
                  {t('history.sign_in_prompt')}
                </p>
              ) : entries.length === 0 ? (
                <p className="text-sm text-zinc-400 text-center px-4 py-8">
                  {t('history.empty')}
                </p>
              ) : (
                <>
                  <HistoryGroup
                    label={t('history.group.today')}
                    entries={groups.today}
                    onSelect={onSelectQuery}
                  />
                  <HistoryGroup
                    label={t('history.group.yesterday')}
                    entries={groups.yesterday}
                    onSelect={onSelectQuery}
                  />
                  <HistoryGroup
                    label={t('history.group.earlier')}
                    entries={groups.earlier}
                    onSelect={onSelectQuery}
                  />
                </>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
