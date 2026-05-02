'use client';

import { useEffect, useMemo, useState } from 'react';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';

export function AuthButton() {
  const { t } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, [supabase]);

  const signIn = () => {
    supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
  };

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  if (loading) {
    return (
      <div className="w-20 h-8 rounded-full bg-zinc-200 animate-pulse" />
    );
  }

  if (!user) {
    return (
      <button
        onClick={signIn}
        className="text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white rounded-full px-3 py-1.5 transition-colors"
      >
        {t('header.sign_in')}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {user.user_metadata?.avatar_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={user.user_metadata.avatar_url as string}
          alt="avatar"
          className="w-7 h-7 rounded-full border border-zinc-200"
          referrerPolicy="no-referrer"
        />
      ) : (
        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
          {(user.email ?? 'U')[0].toUpperCase()}
        </div>
      )}
      <button
        onClick={signOut}
        className="text-xs font-semibold text-zinc-500 hover:text-zinc-800 transition-colors"
      >
        {t('header.sign_out')}
      </button>
    </div>
  );
}
