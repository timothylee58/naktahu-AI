'use client';

import { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/api-base';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';

export interface DailyQuota {
  used: number;
  limit: number;
}

interface QuotaResponse {
  used: number;
  limit: number | null;
  unlimited: boolean;
  authenticated: boolean;
}

// Display-only mirror of the server's daily free quota. Enforcement lives in
// the API (429 on the query endpoint); a failed fetch just hides the meter.
// Returns null for signed-in users: the homepage shows the meter to guests.
export function useDailyQuota(): { quota: DailyQuota | null; refresh: () => void } {
  const { user, ready } = useSupabaseSession();
  const [quota, setQuota] = useState<DailyQuota | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!ready) return;
    if (user) {
      setQuota(null);
      return;
    }
    const controller = new AbortController();
    fetch(`${API_BASE}/api/v1/quota/daily`, { signal: controller.signal })
      .then((res) => (res.ok ? (res.json() as Promise<QuotaResponse>) : null))
      .then((body) => {
        if (body && !body.unlimited && body.limit !== null) setQuota({ used: body.used, limit: body.limit });
        else setQuota(null);
      })
      .catch(() => setQuota(null));
    return () => controller.abort();
  }, [ready, user, tick]);

  return { quota, refresh: () => setTick((n) => n + 1) };
}
