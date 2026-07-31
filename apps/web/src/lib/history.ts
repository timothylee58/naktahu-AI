import type { SupabaseClient } from '@supabase/supabase-js';
import { fetchWithAuth } from '@/lib/auth-headers';
import { API_BASE } from '@/lib/api-base';

export interface HistoryEntry {
  query: string;
  language: string;
  domain: string;
  response_summary: string;
  citations: unknown[];
  ts?: number;
}

export class HistoryFetchError extends Error {
  constructor(
    message: string,
    readonly code: 'pro_required' | 'auth' | 'generic',
  ) {
    super(message);
    this.name = 'HistoryFetchError';
  }
}

async function parseHistoryResponse(res: Response): Promise<HistoryEntry[]> {
  if (res.status === 403) {
    throw new HistoryFetchError('pro_required', 'pro_required');
  }
  if (res.status === 401) {
    throw new HistoryFetchError('auth', 'auth');
  }
  if (!res.ok) {
    throw new HistoryFetchError('generic', 'generic');
  }
  return res.json() as Promise<HistoryEntry[]>;
}

/** @deprecated Prefer fetchHistoryAuthed — avoids stale JWT in SWR keys. */
export async function fetchHistory(accessToken: string): Promise<HistoryEntry[]> {
  const res = await fetch(`${API_BASE}/api/v1/history`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return parseHistoryResponse(res);
}

/** Fetch history with live session token + 401 refresh retry. */
export async function fetchHistoryAuthed(supabase: SupabaseClient): Promise<HistoryEntry[]> {
  const res = await fetchWithAuth(supabase, `${API_BASE}/api/v1/history`);
  return parseHistoryResponse(res);
}

export function sidebarHistoryKey(userId: string): readonly ['sidebar-history', string] {
  return ['sidebar-history', userId];
}

export function historyPageKey(userId: string): readonly ['history-page', string] {
  return ['history-page', userId];
}

/** Stable SWR options — avoid refetch loops on focus/errors/token rotation. */
export const HISTORY_SWR_OPTIONS = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  revalidateIfStale: false,
  shouldRetryOnError: false,
  dedupingInterval: 60_000,
  keepPreviousData: true,
} as const;
