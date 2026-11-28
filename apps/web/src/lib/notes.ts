import type { SupabaseClient } from '@supabase/supabase-js';
import { fetchWithAuth } from '@/lib/auth-headers';
import { API_BASE } from '@/lib/api-base';

const NOTES_URL = `${API_BASE}/api/v1/notes`;

export interface NoteSourceCitation {
  title: string;
  ministry: string;
  url?: string | null;
  effective_date?: string | null;
}

export interface NoteSource {
  query: string;
  citations: NoteSourceCitation[];
}

export interface NoteSummary {
  id: string;
  title: string;
  tags: string[];
  snippet: string;
  from_answer: boolean;
  updated_at: string;
}

export interface Note {
  id: string;
  title: string;
  body: string;
  tags: string[];
  source: NoteSource | null;
  created_at: string;
  updated_at: string;
}

export class NotesError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function check(res: Response): Promise<Response> {
  if (res.ok) return res;
  const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
  throw new NotesError(res.status, typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
}

export async function listNotes(
  supabase: SupabaseClient,
  opts: { q?: string; tag?: string } = {},
): Promise<NoteSummary[]> {
  const params = new URLSearchParams();
  if (opts.q?.trim()) params.set('q', opts.q.trim().slice(0, 200));
  if (opts.tag?.trim()) params.set('tag', opts.tag.trim().slice(0, 40));
  const qs = params.toString();
  const res = await check(await fetchWithAuth(supabase, qs ? `${NOTES_URL}?${qs}` : NOTES_URL));
  return ((await res.json()) as { notes: NoteSummary[] }).notes;
}

export async function getNote(supabase: SupabaseClient, id: string): Promise<Note> {
  const res = await check(await fetchWithAuth(supabase, `${NOTES_URL}/${encodeURIComponent(id)}`));
  return (await res.json()) as Note;
}

export interface NoteDraft {
  title: string;
  body: string;
  tags: string[];
  source?: NoteSource | null;
}

export async function createNote(supabase: SupabaseClient, draft: NoteDraft): Promise<Note> {
  const res = await check(
    await fetchWithAuth(supabase, NOTES_URL, {
      method: 'POST',
      body: JSON.stringify({ ...draft, source: draft.source ?? undefined }),
    }),
  );
  return (await res.json()) as Note;
}

export async function updateNote(
  supabase: SupabaseClient,
  id: string,
  changes: Partial<Pick<NoteDraft, 'title' | 'body' | 'tags'>>,
): Promise<Note> {
  const res = await check(
    await fetchWithAuth(supabase, `${NOTES_URL}/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),
  );
  return (await res.json()) as Note;
}

export async function deleteNote(supabase: SupabaseClient, id: string): Promise<void> {
  await check(await fetchWithAuth(supabase, `${NOTES_URL}/${encodeURIComponent(id)}`, { method: 'DELETE' }));
}

/** Tags typed as "tax, epf" -> ["tax", "epf"]; the server normalises again. */
export function parseTags(raw: string): string[] {
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 10);
}

export interface LinkedNote {
  id: string | null; // null = a [[link]] to a note that doesn't exist yet
  title: string;
}

export interface NoteLinks {
  outgoing: LinkedNote[];
  backlinks: LinkedNote[];
}

export type StaleReason = 'superseded' | 'expired' | 'newer_version';

export interface StaleNote {
  id: string;
  title: string;
  reasons: StaleReason[];
}

export async function getNoteLinks(supabase: SupabaseClient, id: string): Promise<NoteLinks> {
  const res = await check(await fetchWithAuth(supabase, `${NOTES_URL}/${encodeURIComponent(id)}/links`));
  return (await res.json()) as NoteLinks;
}

export async function listStaleNotes(supabase: SupabaseClient): Promise<StaleNote[]> {
  const res = await check(await fetchWithAuth(supabase, `${NOTES_URL}/stale`));
  return ((await res.json()) as { stale: StaleNote[] }).stale;
}

/** Downloads every note as a zip of markdown files (opens in Obsidian as-is). */
export async function exportNotes(supabase: SupabaseClient): Promise<void> {
  const res = await check(await fetchWithAuth(supabase, `${NOTES_URL}/export`));
  const url = URL.createObjectURL(await res.blob());
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = 'naktahu-notes.zip';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}
