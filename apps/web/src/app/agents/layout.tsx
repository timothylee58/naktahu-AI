'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';

export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  if (loading) {
    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-[#0A0F1E] flex items-center justify-center">
        <div className="h-10 w-48 rounded-xl bg-zinc-200 dark:bg-white/10 animate-pulse" />
      </main>
    );
  }

  if (!user) {
    return (
      <main className="min-h-screen bg-zinc-50 dark:bg-[#0A0F1E] flex flex-col items-center justify-center px-4 gap-4">
        <h1 className="text-lg font-bold text-zinc-900 dark:text-white">{t('agents.hub.title')}</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 text-center max-w-sm">{t('agents.hub.sign_in')}</p>
        <Link
          href="/chat"
          className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors text-white text-sm font-semibold"
        >
          {t('header.sign_in')}
        </Link>
      </main>
    );
  }

  return <>{children}</>;
}
