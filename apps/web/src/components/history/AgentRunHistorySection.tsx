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
  explained: 'text-green-600 dark:text-green-400',
  awaiting_hitl: 'text-amber-600 dark:text-amber-400',
  needs_input: 'text-amber-600 dark:text-amber-400',
  running: 'text-zinc-500 dark:text-zinc-400',
  no_questions: 'text-zinc-500 dark:text-zinc-400',
  error: 'text-red-600 dark:text-red-400',
};

// t() falls back to returning the raw key string when a translation is
// missing (see useI18n's implementation) — with completion_status values
// coming straight from each agent's own node code (confirmed: completed,
// explained, needs_input, no_questions, awaiting_hitl, plus whatever an
// agent might set on error), a status this component doesn't have a
// specific label for must fall back to a generic "unknown" label instead
// of rendering "history.agent_runs.status.some_new_value" as visible text.
function statusLabel(t: (key: string) => string, status: string): string {
  const key = `history.agent_runs.status.${status}`;
  const resolved = t(key);
  return resolved === key ? t('history.agent_runs.status.unknown') : resolved;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

// GET /api/v1/agent-runs (plain-auth, not pro-gated) surfaces real
// previously-logged runs — agent_runner.py's _log_run() has been writing
// every start/continue call to `agent_runs` all along; this section is
// the first place that reads it back for a user to revisit past drafts
// and checklists. Each entry links to its agent page with ?run=<id> —
// every agent page reads that param on mount, fetches the stored run via
// useAgentApi().get(`/api/v1/agent-runs/${runId}`) (same authed-fetch
// pattern every one of those pages already uses for everything else), and
// renders straight into its results view instead of starting the intake
// fresh (real resume, not just a fresh agent link). Agents that support
// further conversation (compliance-
// drafter, study-agent, immigration-navigator, grant-finder,
// retrenchment-navigator) also restore session_id so a follow-up message
// continues the real LangGraph thread rather than starting a new one.
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
                href={`/agents/${slug}?run=${encodeURIComponent(run.id)}`}
                className={`block rounded-xl px-4 py-3 flex flex-col gap-1 shadow-sm border transition-colors ${
                  isDark ? 'bg-white/5 border-white/10 hover:bg-white/10' : 'bg-white border-zinc-100 hover:bg-zinc-50'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-sm font-medium ${isDark ? 'text-zinc-200' : 'text-zinc-800'}`}>
                    {t(agentTitleKey(slug))}
                  </span>
                  <span className={`text-[10px] font-semibold uppercase ${statusClass}`}>
                    {statusLabel(t, run.completion_status)}
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
