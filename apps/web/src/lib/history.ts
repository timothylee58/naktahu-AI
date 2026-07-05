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

export async function fetchHistory(accessToken: string): Promise<HistoryEntry[]> {
  const res = await fetch('/api/v1/history', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
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
