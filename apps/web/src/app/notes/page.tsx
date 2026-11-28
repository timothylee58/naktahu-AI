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
  getNote,
  listNotes,
  NotesError,
  parseTags,
  updateNote,
  type Note,
  type NoteSummary,
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

  const open = async (id: string) => {
    setError(null);
    setConfirmDelete(false);
    try {
      const n = await getNote(supabase, id);
      setEditing({ id: n.id, title: n.title, body: n.body, tags: n.tags.join(', '), source: n.source });
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
              <Button type="button" size="sm" onClick={() => { setEditing(BLANK); setConfirmDelete(false); setError(null); }}>
                {t('notes.new')}
              </Button>
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
