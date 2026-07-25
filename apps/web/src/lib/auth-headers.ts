import type { Session, SupabaseClient } from '@supabase/supabase-js';

// Wide buffer so proactive refresh fires well before expiry rather than
// relying on the reactive 401 retry below — some browsers (e.g. Opera)
// don't fully implement Navigator LockManager, which gotrue-js uses for
// cross-tab refresh coordination; when that lock silently fails, a
// refreshSession() call made right at the edge of expiry can miss the
// window entirely, so a large buffer gives it more chances to succeed.
const REFRESH_BUFFER_SEC = 300;

function sessionAccessToken(session: Session | null | undefined): string | null {
  return session?.access_token ?? null;
}

function sessionNeedsRefresh(session: Session | null | undefined): boolean {
  if (!session?.expires_at) return false;
  const now = Math.floor(Date.now() / 1000);
  return session.expires_at - now < REFRESH_BUFFER_SEC;
}

/** Returns a valid access token, refreshing proactively when near expiry. */
export async function getAccessToken(supabase: SupabaseClient): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  let session = data.session;

  if (!session) return null;

  if (sessionNeedsRefresh(session)) {
    const { data: refreshed, error } = await supabase.auth.refreshSession();
    if (!error && refreshed.session) {
      session = refreshed.session;
    }
  }

  return sessionAccessToken(session);
}

export async function getAuthHeaders(supabase: SupabaseClient): Promise<HeadersInit> {
  const token = await getAccessToken(supabase);
  if (!token) throw new Error('sign-in-required');
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

/** Authenticated fetch with one 401 retry after refreshSession(). */
export async function fetchWithAuth(
  supabase: SupabaseClient,
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const headers = await getAuthHeaders(supabase);
  const mergedHeaders = { ...headers, ...(init?.headers as Record<string, string> | undefined) };

  let res = await fetch(input, { ...init, headers: mergedHeaders });
  if (res.status !== 401) return res;

  const { data, error } = await supabase.auth.refreshSession();
  let retryToken = sessionAccessToken(data.session);

  // refreshSession() can fail on browsers with a non-compliant Navigator
  // LockManager (gotrue-js uses it to coordinate cross-tab refresh) even
  // though a valid session still exists — fall back to a plain getSession()
  // read, which doesn't take that lock, before giving up.
  if (error || !retryToken) {
    const fallback = await supabase.auth.getSession();
    retryToken = sessionAccessToken(fallback.data.session);
  }
  if (!retryToken) return res;

  const retryHeaders = {
    ...mergedHeaders,
    Authorization: `Bearer ${retryToken}`,
  };
  res = await fetch(input, { ...init, headers: retryHeaders });
  return res;
}

export function mapApiErrorDetail(detail: string | undefined, t: (key: string) => string): string {
  if (!detail) return t('agents.error.generic');
  if (detail === 'Not authenticated' || detail === 'sign-in-required') {
    return t('agents.error.sign_in');
  }
  if (detail === 'Invalid or expired token') {
    return t('agents.error.session_expired');
  }
  return detail;
}
