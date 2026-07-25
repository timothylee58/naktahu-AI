'use client';

import { useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { fetchWithAuth } from '@/lib/auth-headers';

export function useAgentApi() {
  const supabase = createClient();

  const post = useCallback(
    async (path: string, body: Record<string, unknown>) => {
      const res = await fetchWithAuth(supabase, path, {
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

  return { start, continue: cont, post };
}
