import type { Session, SupabaseClient } from '@supabase/supabase-js';

const REFRESH_BUFFER_SEC = 60;

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
  const retryToken = sessionAccessToken(data.session);
  if (error || !retryToken) return res;

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
