const STORAGE_KEY = 'naktahu_anon_id';

let memorySessionId: string | null = null;

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for non-secure contexts where crypto.randomUUID is unavailable.
  return `${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`;
}

/**
 * Stable per-browser id for grouping anonymous activity (feedback, rate
 * limiting context) without requiring auth. Not a security boundary — never
 * used for anything the backend trusts on its own.
 */
export function getAnonSessionId(): string {
  if (typeof window === 'undefined') return 'server';
  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = generateUUID();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    // localStorage can throw in private-browsing/strict-privacy modes —
    // fall back to an in-memory id that lasts for the page's lifetime.
    if (!memorySessionId) memorySessionId = generateUUID();
    return memorySessionId;
  }
}
