'use client';

import Link from 'next/link';
import useSWR from 'swr';
import { useI18n } from '@/lib/i18n';
import {
  agentRunsPageKey,
  fetchAgentRunsAuthed,
  HISTORY_SWR_OPTIONS,
  type AgentRunEntry,
} from '@/lib/history';
import { agentSlugFromBackendName, agentTitleKey } from '@/lib/agents';
import type { SupabaseClient } from '@supabase/supabase-js';

interface AgentRunHistorySectionProps {
  supabase: SupabaseClient;
  userId: string;
  isDark: boolean;
}

const STATUS_STYLE: Record<string, string> = {
  completed: 'text-green-600 dark:text-green-400',
  awaiting_hitl: 'text-amber-600 dark:text-amber-400',
  running: 'text-zinc-500 dark:text-zinc-400',
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

// GET /api/v1/agent-runs (plain-auth, not pro-gated) surfaces real
// previously-logged runs — agent_runner.py's _log_run() has been writing
// every start/continue call to `agent_runs` all along; this section is
// the first place that reads it back for a user to revisit past drafts
// and checklists. Deliberately NOT full mid-conversation resume (opening
// an entry links to the agent's own page fresh, not back into that exact
// LangGraph thread) — that would need every one of the 9 agent pages to
// accept a ?session= param and call their own get_status endpoint on
// mount, a larger follow-up if wanted. This shows the real stored output
// inline instead, which is honest about what's actually being offered.
export function AgentRunHistorySection({ supabase, userId, isDark }: AgentRunHistorySectionProps) {
  const { t } = useI18n();
  const { data: runs = [], isLoading, error } = useSWR<AgentRunEntry[]>(
    agentRunsPageKey(userId),
    () => fetchAgentRunsAuthed(supabase),
    HISTORY_SWR_OPTIONS,
  );

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2].map((n) => (
          <div key={n} className={`h-16 rounded-xl animate-pulse ${isDark ? 'bg-white/5' : 'bg-zinc-100'}`} />
        ))}
      </div>
    );
  }

  if (error || runs.length === 0) {
    return null;
  }

  return (
    <section className="flex flex-col gap-2">
      <h2 className={`text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
        {t('history.agent_runs.title')}
      </h2>
      <ul className="flex flex-col gap-1">
        {runs.map((run) => {
          const slug = agentSlugFromBackendName(run.agent_name);
          const statusClass = STATUS_STYLE[run.completion_status] ?? STATUS_STYLE.running;
          return (
            <li key={run.id}>
              <Link
                href={`/agents/${slug}`}
                className={`block rounded-xl px-4 py-3 flex flex-col gap-1 shadow-sm border transition-colors ${
                  isDark ? 'bg-white/5 border-white/10 hover:bg-white/10' : 'bg-white border-zinc-100 hover:bg-zinc-50'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-sm font-medium ${isDark ? 'text-zinc-200' : 'text-zinc-800'}`}>
                    {t(agentTitleKey(slug))}
                  </span>
                  <span className={`text-[10px] font-semibold uppercase ${statusClass}`}>
                    {t(`history.agent_runs.status.${run.completion_status}`)}
                  </span>
                </div>
                <span className={`text-xs ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                  {formatDate(run.created_at)} · {t('history.agent_runs.turns').replace('{n}', String(run.turns_count))}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
