'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import useSWR from 'swr';
import type { User } from '@supabase/supabase-js';
import {
  Home,
  Info,
  HelpCircle,
  CreditCard,
  Plug,
  Bot,
  Soup,
  Moon,
  Sun,
  Globe,
  UserRound,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronRight,
  X,
  Pencil,
  Trash2,
  MoreVertical,
  type LucideIcon,
} from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { AuthButton } from '@/components/auth/AuthButton';
import { DeadlineWidget } from '@/components/agents/DeadlineWidget';
import { NakTahuWordmark } from '@/components/logo/NakTahuWordmark';
import { LangToggle } from '@/components/LangToggle';
import { ThemeToggle } from '@/components/ThemeToggle';
import { SiteNavLinks } from '@/components/layout/SiteNavLinks';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import {
  fetchHistoryAuthed,
  deleteHistoryEntry,
  renameHistoryEntry,
  HistoryFetchError,
  HISTORY_SWR_OPTIONS,
  sidebarHistoryKey,
  type HistoryEntry,
} from '@/lib/history';
import { canAccessHistory } from '@/lib/auth-plan';

export interface AppSidebarProps {
  variant?: 'light' | 'dark';
  isMobileOpen: boolean;
  onMobileClose: () => void;
  showHistory?: boolean;
  user?: User | null;
  accessToken?: string | null;
  onSelectQuery?: (entry: HistoryEntry) => void;
  /** Desktop-only: whether the persistent panel is collapsed (hidden). */
  collapsed?: boolean;
  onToggleCollapse?: () => void;
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
  onDelete,
  onRename,
  isDark,
}: {
  entry: HistoryEntry;
  onClick: () => void;
  /** Absent when entry.id is missing (pre-migration-029 row) — menu hides the actions instead of failing silently on click. */
  onDelete?: (entryId: string) => Promise<void>;
  onRename?: (entryId: string, title: string) => Promise<void>;
  isDark: boolean;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [busy, setBusy] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);
  const colors = isDark ? DOMAIN_COLORS_DARK : DOMAIN_COLORS_LIGHT;
  const domainClass = colors[entry.domain] ?? colors['general'];
  const hoverClass = isDark ? 'hover:bg-white/10' : 'hover:bg-zinc-100';
  const textClass = isDark ? 'text-zinc-200' : 'text-zinc-800';
  const mutedClass = isDark ? 'text-zinc-500' : 'text-zinc-400';
  const menuBg = isDark ? 'bg-[#1a1f2e] border-white/15' : 'bg-white border-zinc-200';
  const menuItemHover = isDark ? 'hover:bg-white/10' : 'hover:bg-zinc-100';
  const menuText = isDark ? 'text-zinc-200' : 'text-zinc-700';
  const inputClass = isDark
    ? 'bg-white/10 border-white/20 text-zinc-100 placeholder:text-zinc-500'
    : 'bg-white border-zinc-300 text-zinc-900 placeholder:text-zinc-400';

  const summary = entry.response_summary?.trim();
  const headline = entry.title?.trim() || summary || entry.query;

  // Close menu on click outside
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  useEffect(() => {
    if (renaming) renameInputRef.current?.focus();
  }, [renaming]);

  const startRename = () => {
    setRenameValue(entry.title?.trim() || headline);
    setRenaming(true);
    setMenuOpen(false);
  };

  const commitRename = async () => {
    const title = renameValue.trim();
    if (!title || !entry.id || !onRename) {
      setRenaming(false);
      return;
    }
    setBusy(true);
    try {
      await onRename(entry.id, title);
    } finally {
      setBusy(false);
      setRenaming(false);
    }
  };

  const handleDelete = async () => {
    setMenuOpen(false);
    if (!entry.id || !onDelete) return;
    if (!window.confirm('Delete this history entry?')) return;
    setBusy(true);
    try {
      await onDelete(entry.id);
    } finally {
      setBusy(false);
    }
  };

  if (renaming) {
    return (
      <div className="px-3 py-1.5">
        <input
          ref={renameInputRef}
          value={renameValue}
          disabled={busy}
          onChange={(e) => setRenameValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void commitRename();
            if (e.key === 'Escape') setRenaming(false);
          }}
          onBlur={() => void commitRename()}
          className={`w-full text-sm rounded-md border px-2 py-1 focus:outline-none focus:ring-1 focus:ring-nk-official ${inputClass}`}
          maxLength={150}
        />
      </div>
    );
  }

  return (
    <div className="relative group">
      <button
        onClick={onClick}
        disabled={busy}
        title={summary ? `${headline}\n${entry.query}` : headline}
        className={`w-full text-left px-3 py-2 rounded-lg transition-colors flex flex-col gap-0.5 disabled:opacity-50 ${hoverClass}`}
      >
        <div className="flex items-start justify-between gap-1">
          <span className={`text-sm leading-snug line-clamp-2 ${textClass}`}>
            {truncate(headline, 68)}
          </span>
        </div>
        {summary && (
          <span className={`text-[11px] leading-snug line-clamp-1 ${mutedClass}`}>
            {truncate(entry.query, 48)}
          </span>
        )}
        <span className={`self-start text-[10px] font-semibold px-1.5 py-0.5 rounded locale-nowrap mt-0.5 ${domainClass}`}>
          {entry.domain}
        </span>
      </button>

      {/* Context menu trigger — hidden when there's no id to act on (row predates migration 029) */}
      {entry.id && (onDelete || onRename) && (
        <button
          onClick={(e) => { e.stopPropagation(); setMenuOpen(!menuOpen); }}
          className={`absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity ${isDark ? 'hover:bg-white/15 text-zinc-400' : 'hover:bg-zinc-200 text-zinc-400'}`}
          aria-label="Options"
        >
          <MoreVertical size={14} strokeWidth={1.75} />
        </button>
      )}

      {/* Context menu dropdown */}
      {menuOpen && (
        <div
          ref={menuRef}
          className={`absolute top-8 right-2 z-50 w-40 rounded-lg border shadow-lg py-1 ${menuBg}`}
        >
          {onRename && (
            <button
              onClick={(e) => { e.stopPropagation(); startRename(); }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs ${menuText} ${menuItemHover} transition-colors`}
            >
              <Pencil size={14} strokeWidth={1.75} />
              <span>Rename</span>
            </button>
          )}
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); void handleDelete(); }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-500 ${menuItemHover} transition-colors`}
            >
              <Trash2 size={14} strokeWidth={1.75} />
              <span>Delete</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function HistoryGroup({
  label,
  entries,
  onSelect,
  onDelete,
  onRename,
  isDark,
}: {
  label: string;
  entries: HistoryEntry[];
  onSelect: (entry: HistoryEntry) => void;
  onDelete?: (entryId: string) => Promise<void>;
  onRename?: (entryId: string, title: string) => Promise<void>;
  isDark: boolean;
}) {
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className={`text-[11px] font-semibold uppercase tracking-wider px-3 locale-nowrap ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
        {label}
      </span>
      {entries.map((e, i) => (
        <HistoryRow
          key={e.id ?? i}
          entry={e}
          onClick={() => onSelect(e)}
          onDelete={onDelete}
          onRename={onRename}
          isDark={isDark}
        />
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
  onSelectQuery?: (entry: HistoryEntry) => void;
  onClose?: () => void;
  onCollapse?: () => void;
}) {
  const { t } = useI18n();
  const isDark = variant === 'dark';
  const supabase = useMemo(() => createClient(), []);
  const pathname = usePathname();
  // The CTA's whole point is "jump into a chat" — pointless (and one extra
  // no-op click) on the page that already IS the chat. Every other app
  // page (agents, history, billing, etc.) still gets it.
  const onChatPage = pathname === '/chat';

  const historyEnabled = Boolean(showHistory && user && canAccessHistory(user));

  const { data: entries = [], isLoading: historyLoading, error: historyError, mutate } = useSWR<HistoryEntry[]>(
    historyEnabled && user ? sidebarHistoryKey(user.id) : null,
    () => fetchHistoryAuthed(supabase),
    HISTORY_SWR_OPTIONS,
  );

  const groups = useMemo(() => groupEntries(entries), [entries]);
  // Collapsed by default — history is secondary/return content, not
  // something that should compete with primary nav for vertical space
  // every time the sidebar opens.
  const [historyOpen, setHistoryOpen] = useState(false);

  const handleDeleteEntry = async (entryId: string) => {
    await deleteHistoryEntry(supabase, entryId);
    await mutate((current) => (current ?? []).filter((e) => e.id !== entryId), { revalidate: false });
  };

  const handleRenameEntry = async (entryId: string, title: string) => {
    await renameHistoryEntry(supabase, entryId, title);
    await mutate(
      (current) => (current ?? []).map((e) => (e.id === entryId ? { ...e, title } : e)),
      { revalidate: false },
    );
  };

  const headerBorder = isDark ? 'border-white/10' : 'border-zinc-100';
  const footerBorder = isDark ? 'border-white/10 bg-[#12151C]/80' : 'border-zinc-100 bg-zinc-50/80';
  const titleClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const closeHover = isDark ? 'hover:bg-white/10 text-zinc-400 hover:text-zinc-200' : 'hover:bg-zinc-100 text-zinc-400 hover:text-zinc-700';
  const mutedText = isDark ? 'text-zinc-400' : 'text-zinc-500';

  return (
    <>
      <div className={`flex items-center justify-between px-4 py-3 border-b flex-shrink-0 ${headerBorder}`}>
        <Link href="/chat" className={`inline-flex items-center text-sm ${titleClass}`}>
          <NakTahuWordmark markSize={22} />
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
              <PanelLeftClose size={18} strokeWidth={1.75} />
            </button>
          )}
          {/* close — mobile overlay only */}
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close sidebar"
              className={`p-1 rounded lg:hidden ${closeHover}`}
            >
              <X size={18} strokeWidth={1.75} />
            </button>
          )}
        </div>
      </div>

      <div className={`flex-shrink-0 px-2 py-2 border-b ${headerBorder}`}>
        <SiteNavLinks
          variant={variant}
          layout="vertical"
          onNavigate={onClose}
          showChatCta={!onChatPage}
        />
      </div>

      {showHistory && (
        <div className="flex-1 overflow-y-auto px-2 py-3 flex flex-col gap-3 min-h-0">
          <DeadlineWidget accessToken={accessToken} variant={variant} />

          {/* Collapsed by default — history is secondary content that
              shouldn't compete with primary nav for space. Its own
              background-shade boundary + scroll region (not just a label)
              makes the demotion legible even when expanded. */}
          <div className={`rounded-xl border ${isDark ? 'border-white/5 bg-black/10' : 'border-zinc-100 bg-zinc-50'}`}>
            <button
              type="button"
              onClick={() => setHistoryOpen((o) => !o)}
              className={`w-full flex items-center gap-2 px-3 py-2.5 text-xs font-semibold uppercase tracking-wider locale-nowrap transition-colors ${
                isDark ? 'text-zinc-400 hover:text-zinc-200' : 'text-zinc-500 hover:text-zinc-700'
              }`}
              aria-expanded={historyOpen}
            >
              <span className="flex-1 text-left">{t('history.title')}</span>
              <ChevronRight
                size={16}
                strokeWidth={1.75}
                className={`transition-transform duration-150 ${historyOpen ? 'rotate-90' : ''}`}
              />
            </button>

            {historyOpen && (
              <div className="px-2 pb-2 max-h-72 overflow-y-auto flex flex-col gap-3">
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
                      className="text-xs font-medium text-nk-official-dim hover:text-nk-official transition-colors locale-nowrap"
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
                        className="text-xs font-medium text-nk-official-dim hover:text-nk-official transition-colors locale-nowrap"
                      >
                        {t('nav.pricing')}
                      </Link>
                    ) : (
                      <button
                        onClick={() => mutate()}
                        className="text-xs font-medium text-nk-official-dim hover:text-nk-official transition-colors locale-nowrap"
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
                      onDelete={handleDeleteEntry}
                      onRename={handleRenameEntry}
                      isDark={isDark}
                    />
                    <HistoryGroup
                      label={t('history.group.yesterday')}
                      entries={groups.yesterday}
                      onSelect={(q) => { onSelectQuery?.(q); onClose?.(); }}
                      onDelete={handleDeleteEntry}
                      onRename={handleRenameEntry}
                      isDark={isDark}
                    />
                    <HistoryGroup
                      label={t('history.group.earlier')}
                      entries={groups.earlier}
                      onSelect={(q) => { onSelectQuery?.(q); onClose?.(); }}
                      onDelete={handleDeleteEntry}
                      onRename={handleRenameEntry}
                      isDark={isDark}
                    />
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {!showHistory && (
        <div className="flex-1 min-h-0" />
      )}

      <div className={`flex-shrink-0 border-t px-4 py-3 flex flex-col gap-2 ${footerBorder}`}>
        <div className="flex items-center gap-2">
          <ThemeToggle variant={variant} layout="inline" />
          <LangToggle variant={variant} layout="inline" align="left" />
        </div>
        <AuthButton variant={variant} layout="sidebar" />
      </div>
    </>
  );
}

const RAIL_LINKS: { href: string; Icon: LucideIcon; titleKey: string; community?: boolean }[] = [
  { href: '/', Icon: Home, titleKey: 'nav.home' },
  { href: '/about', Icon: Info, titleKey: 'nav.about' },
  { href: '/faq', Icon: HelpCircle, titleKey: 'nav.faq' },
  { href: '/pricing', Icon: CreditCard, titleKey: 'nav.pricing' },
  { href: '/developer', Icon: Plug, titleKey: 'nav.developer' },
  { href: '/agents', Icon: Bot, titleKey: 'nav.agents' },
  { href: '/warung-watch', Icon: Soup, titleKey: 'nav.warung_watch', community: true },
];

/** Icon-only collapsed rail — desktop only. Secondary controls (language,
 * account) need more room than a rail affords, so their buttons expand the
 * full panel back out rather than trying to cram a dropdown into 3.5rem. */
function SidebarRail({
  variant,
  onExpand,
}: {
  variant: 'light' | 'dark';
  onExpand: () => void;
}) {
  const { t } = useI18n();
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const isDark = variant === 'dark';

  const itemBase = isDark
    ? 'text-zinc-400 hover:text-white hover:bg-white/10'
    : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100';
  const activeItem = isDark ? 'bg-white/10 text-white' : 'bg-zinc-100 text-zinc-900';
  const iconBtn = 'w-9 h-9 flex items-center justify-center rounded-lg transition-colors flex-shrink-0';

  return (
    <div className="flex flex-col items-center h-full py-3 gap-1">
      <button
        onClick={onExpand}
        aria-label={t('sidebar.expand')}
        title={t('sidebar.expand')}
        className={`${iconBtn} mb-2 ${itemBase}`}
      >
        <PanelLeftOpen size={18} strokeWidth={1.75} />
      </button>

      <nav className="flex flex-col items-center gap-1 flex-1 min-h-0">
        {RAIL_LINKS.map((link) => {
          const active = pathname === link.href || (link.href !== '/' && pathname.startsWith(link.href));
          const activeAccent = link.community
            ? (isDark ? 'bg-nk-community/10 text-nk-community' : 'bg-nk-community/10 text-nk-community-dim')
            : activeItem;
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-label={t(link.titleKey)}
              title={t(link.titleKey)}
              className={`${iconBtn} ${active ? activeAccent : itemBase}`}
            >
              <link.Icon size={18} strokeWidth={1.75} aria-hidden />
            </Link>
          );
        })}
      </nav>

      <button
        onClick={toggleTheme}
        aria-label={theme === 'dark' ? t('theme.switch_light') : t('theme.switch_dark')}
        title={theme === 'dark' ? t('theme.switch_light') : t('theme.switch_dark')}
        className={`${iconBtn} ${itemBase}`}
      >
        {theme === 'dark' ? <Moon size={18} strokeWidth={1.75} /> : <Sun size={18} strokeWidth={1.75} />}
      </button>
      <button
        onClick={onExpand}
        aria-label={t('lang.label')}
        title={t('lang.label')}
        className={`${iconBtn} ${itemBase}`}
      >
        <Globe size={18} strokeWidth={1.75} />
      </button>
      <button
        onClick={onExpand}
        aria-label={t('sidebar.account')}
        title={t('sidebar.account')}
        className={`${iconBtn} ${itemBase}`}
      >
        <UserRound size={18} strokeWidth={1.75} />
      </button>
    </div>
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
  collapsed = false,
  onToggleCollapse,
}: AppSidebarProps) {
  const isDark = variant === 'dark';
  const shellClass = isDark
    ? 'bg-[#12151C] border-white/10 text-white'
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
      {/* Persistent panel — desktop. Collapses to an icon-only rail rather
          than hiding entirely, so primary nav stays reachable. */}
      <aside
        className={`hidden lg:flex flex-shrink-0 flex-col border-r h-full transition-[width] duration-150 ${collapsed ? 'w-14' : 'w-72'} ${shellClass}`}
      >
        {collapsed ? (
          <SidebarRail variant={variant} onExpand={() => onToggleCollapse?.()} />
        ) : (
          <SidebarPanel {...panelProps} onCollapse={onToggleCollapse} />
        )}
      </aside>

      {/* Full-page overlay — mobile only */}
      <AnimatePresence>
        {isMobileOpen && (
          <motion.aside
            key="sidebar"
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 34 }}
            className={`fixed inset-0 h-full w-full z-50 flex flex-col lg:hidden ${shellClass}`}
          >
            <SidebarPanel {...panelProps} onClose={onMobileClose} />
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}

/** @deprecated Use AppSidebar */
export const HistorySidebar = AppSidebar;
