'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { fetchWithAuth } from '@/lib/auth-headers';
import { API_BASE } from '@/lib/api-base';
import { useI18n } from '@/lib/i18n';

interface Deadline {
  id: string;
  domain: string;
  deadline_name: string;
  due_date: string;
  recurrence: string | null;
  source_url: string | null;
  last_verified: string | null;
}

const DOMAIN_COLORS: Record<string, string> = {
  tax: 'bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300',
  epf: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
  business: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300',
};

function daysUntil(dateStr: string): number {
  const due = new Date(dateStr).getTime();
  const now = new Date().setHours(0, 0, 0, 0);
  return Math.round((due - now) / 86_400_000);
}

export default function DeadlineMonitorPage() {
  const { t } = useI18n();
  const [deadlines, setDeadlines] = useState<Deadline[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const supabase = createClient();
    fetchWithAuth(supabase, `${API_BASE}/api/v1/agents/deadline-monitor/deadlines`)
      .then((res) => {
        if (res.status === 403) throw new Error('pro-required');
        if (!res.ok) throw new Error('fetch-failed');
        return res.json();
      })
      .then((data: Deadline[]) => {
        if (active) setDeadlines(data);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : 'fetch-failed');
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-white/10 dark:bg-[#0A0F1E]/80">
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-3">
          <Link href="/agents" className="inline-flex items-center gap-1.5 text-sm text-blue-600 transition-colors hover:text-blue-500 dark:text-blue-400 locale-nowrap">
            <ArrowLeft className="h-4 w-4" aria-hidden />
            {t('agents.hub.title')}
          </Link>
          <span className="text-zinc-300 dark:text-white/20" aria-hidden>/</span>
          <h1 className="text-sm font-bold">{t('agents.deadline-monitor.title')}</h1>
        </div>
      </header>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto px-4 py-8 flex flex-col gap-4"
      >
        <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('agents.deadline-monitor.desc')}</p>

        {error === 'pro-required' && (
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('error.history_pro_required')}</p>
            <Link href="/pricing" className="text-sm font-semibold text-blue-600 hover:text-blue-500 transition-colors">
              {t('nav.pricing')}
            </Link>
          </div>
        )}
        {error === 'fetch-failed' && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
            {t('error.history_fetch')}
          </p>
        )}
        {!error && deadlines === null && (
          <div className="flex flex-col gap-2">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-16 rounded-xl animate-pulse bg-zinc-100 dark:bg-white/5" />
            ))}
          </div>
        )}
        {!error && deadlines?.length === 0 && (
          <p className="text-sm text-center py-12 text-zinc-400 dark:text-zinc-500">{t('agents.deadline-monitor.empty')}</p>
        )}
        {!error && deadlines && deadlines.length > 0 && (
          <ul className="flex flex-col gap-2">
            {deadlines.map((d) => {
              const days = daysUntil(d.due_date);
              return (
                <li
                  key={d.id}
                  className="bg-white border border-zinc-200 rounded-xl px-4 py-3 flex flex-col gap-1.5 shadow-sm dark:bg-white/5 dark:border-white/10"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium">{d.deadline_name}</span>
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0 ${DOMAIN_COLORS[d.domain] ?? 'bg-zinc-100 text-zinc-600 dark:bg-white/10 dark:text-zinc-300'}`}>
                      {d.domain}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                    <span>{new Date(d.due_date).toLocaleDateString()}</span>
                    <span>
                      {days < 0
                        ? t('agents.deadline-monitor.overdue')
                        : days === 0
                          ? t('agents.deadline-monitor.today')
                          : `${days} ${t('agents.deadline-monitor.days_left')}`}
                    </span>
                    {d.recurrence && <span>· {d.recurrence}</span>}
                  </div>
                  {d.source_url && (
                    <a href={d.source_url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline dark:text-blue-400 w-fit">
                      {t('agents.deadline-monitor.source')}
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </motion.div>
    </main>
  );
}
