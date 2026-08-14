import type { SupabaseClient } from '@supabase/supabase-js';
import { fetchWithAuth } from '@/lib/auth-headers';
import { API_BASE } from '@/lib/api-base';

export interface HistoryEntry {
  /** Row id (migration 029). Absent on rows written before that migration —
   * the frontend hides rename/delete for entries with no id. */
  id?: string | null;
  /** Custom label set via rename (migration 029); overrides response_summary/query in list headlines when present. */
  title?: string | null;
  query: string;
  language: string;
  domain: string;
  response_summary: string;
  /** Full stored answer text (migration 028). Absent on rows written before
   * that migration — those fall back to re-prompting on click. */
  response_text?: string | null;
  confidence?: number | null;
  suggestions?: string[];
  agency_contact?: {
    agency: string;
    domain: string;
    hotline: string;
    portal: string;
  } | null;
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

/** Delete one history entry. Throws on failure (network/404/503) — callers
 * should catch and surface an error rather than optimistically assume success. */
export async function deleteHistoryEntry(supabase: SupabaseClient, entryId: string): Promise<void> {
  const res = await fetchWithAuth(supabase, `${API_BASE}/api/v1/history/${encodeURIComponent(entryId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete history entry (${res.status})`);
  }
}

/** Rename one history entry (sets a custom display title). Throws on failure. */
export async function renameHistoryEntry(
  supabase: SupabaseClient,
  entryId: string,
  title: string,
): Promise<void> {
  const res = await fetchWithAuth(supabase, `${API_BASE}/api/v1/history/${encodeURIComponent(entryId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    throw new Error(`Failed to rename history entry (${res.status})`);
  }
}

export interface AgentRunEntry {
  id: string;
  agent_name: string;
  session_id: string | null;
  output: Record<string, unknown>;
  completion_status: string;
  turns_count: number;
  created_at: string;
}

/** Fetch past vertical-agent runs (drafts, checklists, eligibility
 * results) — GET /api/v1/agent-runs, plain-auth (not pro-gated like
 * /history above), since the underlying agents span every plan tier. */
export async function fetchAgentRunsAuthed(
  supabase: SupabaseClient,
  agentName?: string,
): Promise<AgentRunEntry[]> {
  const url = agentName
    ? `${API_BASE}/api/v1/agent-runs?agent_name=${encodeURIComponent(agentName)}`
    : `${API_BASE}/api/v1/agent-runs`;
  const res = await fetchWithAuth(supabase, url);
  if (!res.ok) {
    throw new Error(`Failed to fetch agent run history (${res.status})`);
  }
  return res.json() as Promise<AgentRunEntry[]>;
}

export function agentRunsPageKey(userId: string): readonly ['agent-runs-page', string] {
  return ['agent-runs-page', userId];
}

export function agentRunsForAgentKey(
  userId: string,
  agentName: string,
): readonly ['agent-runs-page', string, string] {
  return ['agent-runs-page', userId, agentName];
}

/** sessionStorage key used to hand a clicked HistoryEntry off to /chat for
 * reconstruction as real chat bubbles (see history/page.tsx + chat/page.tsx).
 * sessionStorage (not a URL param) since a full response_text can be long. */
export const HISTORY_RESTORE_STORAGE_KEY = 'naktahu:restore_history_entry';

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
