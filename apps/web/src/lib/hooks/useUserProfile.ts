'use client';

import { useCallback, useEffect, useState } from 'react';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { fetchWithAuth } from '@/lib/auth-headers';
import { API_BASE } from '@/lib/api-base';
import { SAVED_POSTCODE_KEY } from '@/lib/postcode';

/** The saved "about you" profile. Every field is optional: null = not shared. */
export interface UserProfile {
  state: string | null;
  postcode: string | null;
  employment_status: string | null;
  business_type: string | null;
  sector: string | null;
  household_size: number | null;
  /** Opt-in. null means the user chose not to share it. */
  is_bumiputera: boolean | null;
}

export const EMPTY_PROFILE: UserProfile = {
  state: null,
  postcode: null,
  employment_status: null,
  business_type: null,
  sector: null,
  household_size: null,
  is_bumiputera: null,
};

const PROFILE_URL = `${API_BASE}/api/v1/me/profile`;

function pick(raw: Record<string, unknown>): UserProfile {
  const str = (v: unknown) => (typeof v === 'string' && v ? v : null);
  return {
    state: str(raw.state),
    postcode: str(raw.postcode),
    employment_status: str(raw.employment_status),
    business_type: str(raw.business_type),
    sector: str(raw.sector),
    household_size: typeof raw.household_size === 'number' ? raw.household_size : null,
    is_bumiputera: typeof raw.is_bumiputera === 'boolean' ? raw.is_bumiputera : null,
  };
}

/** Keeps the landing page's saved postcode (localStorage) in step with the profile. */
function mirrorPostcode(postcode: string | null): void {
  try {
    if (postcode) localStorage.setItem(SAVED_POSTCODE_KEY, postcode);
  } catch {
    /* storage blocked: the profile itself is still saved */
  }
}

/**
 * Loads and saves the signed-in user's profile. Signed-out visitors get
 * `profile: null` and `signedIn: false`; a failed load also leaves
 * `profile: null`, so callers can simply skip prefill. Never throws.
 */
export function useUserProfile() {
  const { supabase, user, ready } = useSupabaseSession();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!ready) return;
    if (!user?.id) {
      setProfile(null);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    void (async () => {
      try {
        const res = await fetchWithAuth(supabase, PROFILE_URL);
        if (!res.ok) throw new Error(String(res.status));
        const next = pick((await res.json()) as Record<string, unknown>);
        if (active) setProfile(next);
      } catch {
        if (active) setProfile(null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [ready, user?.id, supabase]);

  const save = useCallback(
    async (next: UserProfile): Promise<boolean> => {
      setSaving(true);
      setError(false);
      try {
        const res = await fetchWithAuth(supabase, PROFILE_URL, {
          method: 'PUT',
          body: JSON.stringify(next),
        });
        if (!res.ok) throw new Error(String(res.status));
        const saved = pick((await res.json()) as Record<string, unknown>);
        setProfile(saved);
        mirrorPostcode(saved.postcode);
        return true;
      } catch {
        setError(true); // the form keeps what the user typed; nothing is reverted
        return false;
      } finally {
        setSaving(false);
      }
    },
    [supabase],
  );

  const remove = useCallback(async (): Promise<boolean> => {
    setSaving(true);
    setError(false);
    try {
      const res = await fetchWithAuth(supabase, PROFILE_URL, { method: 'DELETE' });
      if (!res.ok) throw new Error(String(res.status));
      setProfile(EMPTY_PROFILE);
      return true;
    } catch {
      setError(true);
      return false;
    } finally {
      setSaving(false);
    }
  }, [supabase]);

  return { profile, loading, saving, error, signedIn: Boolean(user?.id), save, remove };
}
