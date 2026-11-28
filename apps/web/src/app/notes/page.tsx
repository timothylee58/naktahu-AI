'use client';

export const dynamic = 'force-dynamic';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { NakTahuWordmark } from '@/components/logo/NakTahuWordmark';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  createNote,
  deleteNote,
  exportNotes,
  getNote,
  getNoteLinks,
  listNotes,
  listStaleNotes,
  NotesError,
  parseTags,
  updateNote,
  type Note,
  type NoteLinks,
  type NoteSummary,
  type StaleNote,
} from '@/lib/notes';

type Editing = { id: string | null; title: string; body: string; tags: string; source: Note['source'] };

const BLANK: Editing = { id: null, title: '', body: '', tags: '', source: null };

export default function NotesPage() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const { supabase, user, accessToken, ready } = useSupabaseSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [tag, setTag] = useState('');
  const [editing, setEditing] = useState<Editing | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [links, setLinks] = useState<NoteLinks | null>(null);
  const [stale, setStale] = useState<Record<string, StaleNote>>({});
  const [exporting, setExporting] = useState(false);

  const reload = useCallback(async () => {
    try {
      setNotes(await listNotes(supabase, { q: query, tag }));
      setError(null);
    } catch {
      setError(t('notes.error_load'));
    } finally {
      setLoading(false);
    }
  }, [supabase, query, tag, t]);

  // Debounced so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    if (!ready || !user) {
      setLoading(false);
      return;
    }
    const handle = window.setTimeout(() => void reload(), 250);
    return () => window.clearTimeout(handle);
  }, [ready, user, reload]);

  // Which saved answers cite a source that has since changed. Best effort: if
  // it fails the notes still work, there just are no badges.
  useEffect(() => {
    if (!ready || !user) return;
    let active = true;
    void listStaleNotes(supabase)
      .then((items) => {
        if (active) setStale(Object.fromEntries(items.map((n) => [n.id, n])));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [ready, user, supabase]);

  const loadLinks = useCallback(
    async (id: string) => {
      try {
        setLinks(await getNoteLinks(supabase, id));
      } catch {
        setLinks(null);
      }
    },
    [supabase],
  );

  const onExport = async () => {
    if (exporting) return;
    setExporting(true);
    setError(null);
    try {
      await exportNotes(supabase);
    } catch {
      setError(t('notes.error_export'));
    } finally {
      setExporting(false);
    }
  };

  const open = async (id: string) => {
    setError(null);
    setConfirmDelete(false);
    try {
      const n = await getNote(supabase, id);
      setEditing({ id: n.id, title: n.title, body: n.body, tags: n.tags.join(', '), source: n.source });
      void loadLinks(n.id);
    } catch {
      setError(t('notes.error_load'));
    }
  };

  const onSave = async () => {
    if (!editing || !editing.title.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const tags = parseTags(editing.tags);
      const saved = editing.id
        ? await updateNote(supabase, editing.id, { title: editing.title.trim(), body: editing.body, tags })
        : await createNote(supabase, { title: editing.title.trim(), body: editing.body, tags });
      setEditing({ id: saved.id, title: saved.title, body: saved.body, tags: saved.tags.join(', '), source: saved.source });
      await reload();
      void loadLinks(saved.id);
    } catch (e) {
      // Keep what the user typed; just say what went wrong.
      setError(e instanceof NotesError && e.status === 409 ? e.message : t('notes.error_save'));
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async () => {
    if (!editing?.id || busy) return;
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setBusy(true);
    try {
      await deleteNote(supabase, editing.id);
      setEditing(null);
      setLinks(null);
      setConfirmDelete(false);
      await reload();
    } catch {
      setError(t('notes.error_delete'));
    } finally {
      setBusy(false);
    }
  };

  const muted = isDark ? 'text-zinc-400' : 'text-zinc-500';

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
          <Button type="button" variant="ghost" size="icon" className="lg:hidden" aria-label={t('header.menu')} onClick={() => setSidebarOpen(true)}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden>
              <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
            </svg>
          </Button>
          <Link href="/" className="flex flex-col">
            <NakTahuWordmark markSize={20} className="text-base" />
            <span className={`text-xs ${muted}`}>{t('header.subtitle')}</span>
          </Link>
        </header>

        <main className="flex-1 px-4 py-6 max-w-4xl w-full mx-auto flex flex-col gap-4">
          <div className="flex items-center justify-between gap-2">
            <h1 className={`text-lg font-bold ${isDark ? 'text-white' : 'text-zinc-900'}`}>{t('notes.title')}</h1>
            {user && (
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => void onExport()} disabled={exporting || notes.length === 0}>
                  {exporting ? t('notes.exporting') : t('notes.export')}
                </Button>
                <Button type="button" size="sm" onClick={() => { setEditing(BLANK); setLinks(null); setConfirmDelete(false); setError(null); }}>
                  {t('notes.new')}
                </Button>
              </div>
            )}
          </div>

          {!ready ? (
            <div className={`h-16 rounded-xl animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
          ) : !user ? (
            <p className={`text-sm text-center py-12 ${muted}`}>{t('notes.sign_in')}</p>
          ) : (
            <div className="grid gap-4 md:grid-cols-[minmax(0,18rem)_1fr]">
              <section aria-label={t('notes.title')} className="flex flex-col gap-2">
                <Input
                  type="search"
                  value={query}
                  maxLength={200}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t('notes.search')}
                  aria-label={t('notes.search')}
                />
                {tag && (
                  <Button type="button" variant="outline" size="sm" className="self-start" onClick={() => setTag('')}>
                    #{tag} ✕
                  </Button>
                )}
                {loading ? (
                  <div className={`h-16 rounded-xl animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
                ) : notes.length === 0 ? (
                  <p className={`text-sm py-6 ${muted}`}>{query || tag ? t('notes.no_results') : t('notes.empty')}</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {notes.map((n) => (
                      <li key={n.id}>
                        <button
                          type="button"
                          onClick={() => void open(n.id)}
                          aria-current={editing?.id === n.id}
                          className={`w-full text-left rounded-xl border px-3 py-2 transition-colors ${
                            editing?.id === n.id
                              ? 'border-nk-official/50 bg-nk-official/10'
                              : isDark
                                ? 'border-white/10 hover:bg-white/5'
                                : 'border-zinc-200 bg-white hover:bg-zinc-50'
                          }`}
                        >
                          <span className="block text-sm font-medium line-clamp-1">{n.title}</span>
                          {n.snippet && <span className={`block text-xs line-clamp-2 ${muted}`}>{n.snippet}</span>}
                          <span className="mt-1 flex flex-wrap gap-1">
                            {stale[n.id] && (
                              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-400">
                                {t('notes.stale_badge')}
                              </span>
                            )}
                            {n.from_answer && (
                              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-nk-official/10 text-nk-official-dim dark:text-nk-official">
                                {t('notes.from_answer')}
                              </span>
                            )}
                            {n.tags.map((tg) => (
                              <span
                                key={tg}
                                role="button"
                                tabIndex={0}
                                onClick={(e) => { e.stopPropagation(); setTag(tg); }}
                                onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); setTag(tg); } }}
                                className={`text-[10px] px-1.5 py-0.5 rounded border ${isDark ? 'border-white/10' : 'border-zinc-200'}`}
                              >
                                #{tg}
                              </span>
                            ))}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section aria-label={t('notes.editor')} className="min-w-0">
                {editing ? (
                  <div className={`flex flex-col gap-3 rounded-2xl border p-4 ${isDark ? 'border-white/10 bg-white/5' : 'border-zinc-200 bg-white shadow-sm'}`}>
                    <Input
                      value={editing.title}
                      maxLength={200}
                      onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                      placeholder={t('notes.title_label')}
                      aria-label={t('notes.title_label')}
                    />
                    <Textarea
                      rows={12}
                      value={editing.body}
                      maxLength={20000}
                      onChange={(e) => setEditing({ ...editing, body: e.target.value })}
                      placeholder={t('notes.body_label')}
                      aria-label={t('notes.body_label')}
                    />
                    <Input
                      value={editing.tags}
                      onChange={(e) => setEditing({ ...editing, tags: e.target.value })}
                      placeholder={t('notes.tags_hint')}
                      aria-label={t('notes.tags_label')}
                    />
                    {editing.id && stale[editing.id] && (
                      <p role="status" className="text-xs rounded-lg bg-amber-500/10 px-3 py-2 text-amber-800 dark:text-amber-300">
                        {t('notes.stale_banner')} {stale[editing.id].reasons.map((r) => t(`notes.stale.${r}`)).join(' ')}
                      </p>
                    )}
                    {editing.source && (
                      <div className={`text-xs ${muted}`}>
                        <p className="font-semibold">{t('notes.saved_from')}: {editing.source.query}</p>
                        <ul className="mt-1 flex flex-col gap-0.5">
                          {editing.source.citations.map((c, i) => (
                            <li key={`${c.url ?? c.title}-${i}`}>
                              {c.ministry && <span className="font-mono font-semibold uppercase">{c.ministry} </span>}
                              {c.url ? (
                                <a href={c.url} target="_blank" rel="noopener noreferrer" className="underline">
                                  {c.title || c.url}
                                </a>
                              ) : (
                                c.title
                              )}
                              {c.effective_date && <span> · {t('notes.as_of')} {c.effective_date}</span>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {links && (links.outgoing.length > 0 || links.backlinks.length > 0) && (
                      <div className={`grid gap-2 text-xs sm:grid-cols-2 ${muted}`}>
                        <div>
                          <p className="font-semibold">{t('notes.links_out')}</p>
                          <ul className="mt-1 flex flex-col gap-0.5">
                            {links.outgoing.map((l) => (
                              <li key={`o-${l.title}`}>
                                {l.id ? (
                                  <Button type="button" variant="ghost" size="sm" className="h-auto px-1 py-0.5 underline" onClick={() => void open(l.id as string)}>
                                    {l.title}
                                  </Button>
                                ) : (
                                  <span title={t('notes.link_missing')}>{l.title} ?</span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="font-semibold">{t('notes.links_in')}</p>
                          <ul className="mt-1 flex flex-col gap-0.5">
                            {links.backlinks.map((l) => (
                              <li key={`b-${l.id}`}>
                                <Button type="button" variant="ghost" size="sm" className="h-auto px-1 py-0.5 underline" onClick={() => void open(l.id as string)}>
                                  {l.title}
                                </Button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                      <Button type="button" onClick={() => void onSave()} disabled={busy || !editing.title.trim()}>
                        {busy ? t('notes.saving') : t('notes.save')}
                      </Button>
                      {editing.id && (
                        <Button type="button" variant="outline" onClick={() => void onDelete()} disabled={busy}>
                          {confirmDelete ? t('notes.delete_confirm') : t('notes.delete')}
                        </Button>
                      )}
                      <Button type="button" variant="ghost" onClick={() => setEditing(null)}>
                        {t('notes.close')}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className={`text-sm py-6 ${muted}`}>{t('notes.pick')}</p>
                )}
                {error && <p role="alert" className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
              </section>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
