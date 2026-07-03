const STORAGE_KEY = 'naktahu_anon_id';

/**
 * Stable per-browser id for grouping anonymous activity (feedback, rate
 * limiting context) without requiring auth. Not a security boundary — never
 * used for anything the backend trusts on its own.
 */
export function getAnonSessionId(): string {
  if (typeof window === 'undefined') return 'server';
  let id = localStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}
