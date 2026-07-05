'use client';

import { useEffect, useMemo, useState } from 'react';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';

interface SupabaseSessionState {
  supabase: ReturnType<typeof createClient>;
  user: User | null;
  userId: string | null;
  accessToken: string | null;
  ready: boolean;
}

/** Shared auth listener with stable user identity across token refresh events. */
export function useSupabaseSession(): SupabaseSessionState {
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setAccessToken(data.session?.access_token ?? null);
      setReady(true);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      const nextUser = session?.user ?? null;
      setUser((prev) => (prev?.id === nextUser?.id ? prev : nextUser));
      const nextToken = session?.access_token ?? null;
      setAccessToken((prev) => (prev === nextToken ? prev : nextToken));
    });

    return () => subscription.unsubscribe();
  }, [supabase]);

  return {
    supabase,
    user,
    userId: user?.id ?? null,
    accessToken,
    ready,
  };
}
