'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { createClient } from '@/lib/supabase/client';
import { fetchWithAuth } from '@/lib/auth-headers';
import { API_BASE } from '@/lib/api-base';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
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

// deadline_schedule.domain has no CHECK constraint of its own, but
// migration 023's comment confirms it reuses the canonical 10-domain list
// from 016_widen_domain_constraint.sql (government, education, legal,
// finance, healthcare, epf, tax, business, immigration, culture) — this
// used to cover only 3 of those 10, so any deadline outside tax/epf/
// business silently fell back to plain gray with no visual distinction.
const DOMAIN_COLORS: Record<string, string> = {
  tax: 'bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300',
  epf: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
  business: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300',
  government: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  education: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  legal: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300',
  finance: 'bg-teal-100 text-teal-700 dark:bg-teal-500/15 dark:text-teal-300',
  healthcare: 'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300',
  immigration: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300',
  culture: 'bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-500/15 dark:text-fuchsia-300',
};

// The DB value is 'healthcare' but this app's existing domain.* i18n keys
// (shared with the main query pipeline's domain chips) use 'domain.health'
// — a mismatch that would silently break a direct `domain.${d}` lookup.
// Guards the same way research-synthesiser's domainLabel() does: falls
// back to the raw slug rather than leaking an unresolved i18n key to the
// user if a future domain value has no key at all.
const DOMAIN_KEY_OVERRIDES: Record<string, string> = { healthcare: 'health' };

function recurrenceLabel(t: (key: string) => string, recurrence: string): string {
  const key = `agents.deadline-monitor.recurrence.${recurrence}`;
  const resolved = t(key);
  return resolved === key ? recurrence : resolved;
}

function daysUntil(dateStr: string): number {
  const due = new Date(dateStr).getTime();
  const now = new Date().setHours(0, 0, 0, 0);
  return Math.round((due - now) / 86_400_000);
}

type Urgency = 'overdue' | 'today' | 'soon' | 'normal';

function urgencyOf(days: number): Urgency {
  if (days < 0) return 'overdue';
  if (days === 0) return 'today';
  if (days <= 7) return 'soon';
  return 'normal';
}

const URGENCY_STYLES: Record<Urgency, { card: string; text: string }> = {
  overdue: { card: 'border-red-300 dark:border-red-500/40', text: 'text-red-700 dark:text-red-400 font-semibold' },
  today: { card: 'border-amber-300 dark:border-amber-500/40', text: 'text-amber-700 dark:text-amber-400 font-semibold' },
  soon: { card: 'border-zinc-200 dark:border-white/10', text: 'text-amber-600 dark:text-amber-400 font-medium' },
  normal: { card: 'border-zinc-200 dark:border-white/10', text: 'text-zinc-500 dark:text-zinc-400' },
};

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
    <>
      <AgentPageHeader title={t('agents.deadline-monitor.title')} />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto px-4 py-6 flex flex-col gap-4"
      >
        <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('agents.deadline-monitor.desc')}</p>

        {error === 'pro-required' && (
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('error.history_pro_required')}</p>
            <Link href="/pricing" className="text-sm font-semibold text-nk-official-dim hover:text-nk-official transition-colors">
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
              const urgency = urgencyOf(days);
              const style = URGENCY_STYLES[urgency];
              const domainKey = `domain.${DOMAIN_KEY_OVERRIDES[d.domain] ?? d.domain}`;
              const domainLabel = t(domainKey);
              return (
                <li
                  key={d.id}
                  className={`bg-white border rounded-xl px-4 py-3 flex flex-col gap-1.5 shadow-sm dark:bg-white/5 ${style.card}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium">{d.deadline_name}</span>
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0 ${DOMAIN_COLORS[d.domain] ?? 'bg-zinc-100 text-zinc-600 dark:bg-white/10 dark:text-zinc-300'}`}>
                      {domainLabel === domainKey ? d.domain : domainLabel}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-zinc-500 dark:text-zinc-400">{new Date(d.due_date).toLocaleDateString()}</span>
                    <span className={style.text}>
                      {days < 0
                        ? t('agents.deadline-monitor.overdue')
                        : days === 0
                          ? t('agents.deadline-monitor.today')
                          : `${days} ${t('agents.deadline-monitor.days_left')}`}
                    </span>
                    {d.recurrence && (
                      <span className="text-zinc-500 dark:text-zinc-400">· {recurrenceLabel(t, d.recurrence)}</span>
                    )}
                  </div>
                  {d.source_url && (
                    <a href={d.source_url} target="_blank" rel="noreferrer" className="text-xs text-nk-official-dim hover:underline dark:text-nk-official w-fit">
                      {t('agents.deadline-monitor.source')}
                    </a>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </motion.div>
    </>
  );
}
