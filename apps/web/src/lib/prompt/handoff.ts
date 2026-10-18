export type HandoffSource = 'typed' | 'chip' | 'tile' | 'voice';

export interface PendingPrompt {
  q: string;
  source: HandoffSource;
  uiLocale: 'ms' | 'en' | 'zh';
  ts: number;
}

const KEY = 'nk:pending';
export const HANDOFF_TTL_MS = 5 * 60 * 1000;
export const HANDOFF_MAX_LENGTH = 1000;

// sessionStorage, not the URL: a typed question can contain personal
// details, and URLs end up in history, referrers and server logs.
export function savePending(p: Omit<PendingPrompt, 'ts'>): boolean {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ ...p, ts: Date.now() }));
    return true;
  } catch {
    return false;
  }
}

export function takePending(now: number = Date.now()): PendingPrompt | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as Partial<PendingPrompt>;
    if (typeof p.q !== 'string' || typeof p.ts !== 'number') return null;
    if (now - p.ts > HANDOFF_TTL_MS) return null;
    const q = p.q.trim().slice(0, HANDOFF_MAX_LENGTH);
    if (!q) return null;
    return {
      q,
      source: (p.source as HandoffSource) ?? 'typed',
      uiLocale: (p.uiLocale as PendingPrompt['uiLocale']) ?? 'ms',
      ts: p.ts,
    };
  } catch {
    return null;
  }
}
