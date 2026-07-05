'use client';

import { useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';

export function useAgentApi() {
  const supabase = createClient();

  const authHeaders = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) throw new Error('sign-in-required');
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  }, [supabase]);

  const start = useCallback(
    async (agentName: string, body: Record<string, unknown>) => {
      const headers = await authHeaders();
      const res = await fetch(`/api/v1/agents/${agentName}/start`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(err.detail ?? 'agent-start-failed');
      }
      return res.json() as Promise<Record<string, unknown>>;
    },
    [authHeaders],
  );

  const cont = useCallback(
    async (agentName: string, body: Record<string, unknown>) => {
      const headers = await authHeaders();
      const res = await fetch(`/api/v1/agents/${agentName}/continue`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('agent-continue-failed');
      return res.json() as Promise<Record<string, unknown>>;
    },
    [authHeaders],
  );

  return { start, continue: cont, authHeaders };
}
