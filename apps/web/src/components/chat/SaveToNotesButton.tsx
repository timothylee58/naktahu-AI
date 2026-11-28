'use client';

import { useState } from 'react';
import Link from 'next/link';
import type { Citation } from '@/lib/types';
import { useI18n } from '@/lib/i18n';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { createNote, NotesError, type NoteSourceCitation } from '@/lib/notes';

interface SaveToNotesButtonProps {
  content: string;
  query: string;
  domain?: string;
  citations?: Citation[];
}

function toSourceCitations(citations: Citation[] | undefined): NoteSourceCitation[] {
  return (citations ?? []).slice(0, 10).flatMap((c) => {
    const url = c.url ?? c.source_url ?? '';
    // Only real http(s) source URLs are kept; the server enforces the same.
    return [
      {
        title: (c.title ?? c.source_title ?? '').slice(0, 300),
        ministry: (c.ministry ?? '').slice(0, 200),
        url: /^https?:\/\//i.test(url) ? url.slice(0, 2000) : null,
        effective_date: c.effective_date && /^\d{4}-\d{2}-\d{2}$/.test(c.effective_date) ? c.effective_date : null,
      },
    ];
  });
}

/** Saves this answer, with where it came from, to the signed-in user's notes. */
export function SaveToNotesButton({ content, query, domain, citations }: SaveToNotesButtonProps) {
  const { t } = useI18n();
  const { supabase } = useSupabaseSession();
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const save = async () => {
    if (state === 'saving' || state === 'saved') return;
    setState('saving');
    setMessage(null);
    try {
      await createNote(supabase, {
        title: query.trim().slice(0, 200) || t('notes.untitled'),
        body: content.slice(0, 20000),
        tags: domain && domain !== 'general' ? [domain.slice(0, 40)] : [],
        source: { query: query.slice(0, 2000), citations: toSourceCitations(citations) },
      });
      setState('saved');
    } catch (e) {
      setState('error'); // not saved: the button stays usable for a retry
      setMessage(e instanceof NotesError && e.status === 409 ? e.message : null);
    }
  };

  return (
    <span className="inline-flex items-center gap-1">
      <button
        type="button"
        onClick={() => void save()}
        disabled={state === 'saving' || state === 'saved'}
        title={t('chat.actions.save_note')}
        className="flex items-center gap-1.5 p-1.5 sm:px-2 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 dark:text-zinc-500 dark:hover:text-zinc-200 dark:hover:bg-white/10 transition-colors disabled:cursor-default"
      >
        <span className="text-xs font-medium">
          {state === 'saved' ? t('chat.actions.note_saved') : t('chat.actions.save_note')}
        </span>
      </button>
      {state === 'saved' && (
        <Link href="/notes" className="text-xs font-medium text-nk-official-dim hover:text-nk-official">
          {t('chat.actions.view_notes')}
        </Link>
      )}
      {state === 'error' && (
        <span role="alert" className="text-xs text-red-600 dark:text-red-400">
          {message ?? t('chat.actions.note_error')}
        </span>
      )}
    </span>
  );
}
