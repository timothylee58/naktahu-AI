'use client';

import { useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { fetchWithAuth, getAccessToken } from '@/lib/auth-headers';
import { API_BASE } from '@/lib/api-base';

export function useAgentApi() {
  const supabase = createClient();

  const post = useCallback(
    async (path: string, body: Record<string, unknown>) => {
      const res = await fetchWithAuth(supabase, `${API_BASE}${path}`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(err.detail ?? 'agent-request-failed');
      }
      return res.json() as Promise<Record<string, unknown>>;
    },
    [supabase],
  );

  // Multipart can't go through post()/fetchWithAuth, which force a JSON
  // Content-Type; the browser must set the multipart boundary itself.
  const upload = useCallback(
    async (path: string, form: FormData) => {
      const token = await getAccessToken(supabase);
      if (!token) throw new Error('sign-in-required');
      const res = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(err.detail ?? 'agent-request-failed');
      }
      return res.json() as Promise<Record<string, unknown>>;
    },
    [supabase],
  );

  const start = useCallback(
    async (agentName: string, body: Record<string, unknown>) =>
      post(`/api/v1/agents/${agentName}/start`, body),
    [post],
  );

  const cont = useCallback(
    async (agentName: string, body: Record<string, unknown>) =>
      post(`/api/v1/agents/${agentName}/continue`, body),
    [post],
  );

  const get = useCallback(
    async (path: string) => {
      const res = await fetchWithAuth(supabase, `${API_BASE}${path}`);
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(err.detail ?? 'agent-request-failed');
      }
      return res.json();
    },
    [supabase],
  );

  return { start, continue: cont, post, get, upload };
}
