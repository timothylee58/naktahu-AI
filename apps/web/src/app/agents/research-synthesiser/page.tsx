'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { CitationChip } from '@/components/chat/CitationChip';
import { useI18n } from '@/lib/i18n';
import { agentTitleKey } from '@/lib/agents';
import type { Citation } from '@/lib/types';

// This agent's `language` field is the target language for the synthesised
// answer, not free-text detection (research-synthesiser compiles with no
// LangGraph checkpointer/router_node pass — it's a single-shot fan-out, see
// the resume-effect comment below). Deriving it from the active UI locale
// instead of hardcoding 'bm' follows the same precedented pattern already
// used by grant-draft-generator and sme-compliance-navigator's `queryLanguage`.
function localeToApiLanguage(locale: string): 'bm' | 'en' | 'zh' {
  if (locale === 'ms') return 'bm';
  if (locale === 'zh') return 'zh';
  return 'en';
}

function ResearchSynthesiserPageInner() {
  const { t, locale } = useI18n();
  const { start, get } = useAgentApi();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState('');
  const [citations, setCitations] = useState<Array<Record<string, unknown>>>([]);
  const [domains, setDomains] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planRequired, setPlanRequired] = useState<string | null>(null);
  // Distinguishes "never run yet" from "ran, found nothing" — the backend
  // (graph.py) is pure parallel RAG citation aggregation with no LLM
  // synthesis step, so a query that matches nothing in the corpus legitimately
  // comes back with domains but zero citations. Previously that rendered as
  // an empty page with no feedback, indistinguishable from the form having
  // done nothing at all.
  const [hasRun, setHasRun] = useState(false);

  const run = async () => {
    setLoading(true);
    setError(null);
    setPlanRequired(null);
    try {
      const res = await start('research-synthesiser', { query, language: localeToApiLanguage(locale) });
      setCitations((res.citations as Array<Record<string, unknown>>) ?? []);
      setDomains((res.detected_domains as string[]) ?? []);
      setHasRun(true);
    } catch (e) {
      // Backend's plan gate (routers/agents.py::_require_agent_access) always
      // phrases its 403 as "This agent requires the <plan> plan or higher." —
      // matched here rather than a raw status code because useAgentApi's
      // post() only preserves the message, not the response status. Any
      // other failure (network, 5xx) falls through to the generic banner.
      const message = e instanceof Error ? e.message : '';
      const match = /requires the (\w+) plan/i.exec(message);
      if (match) {
        setPlanRequired(match[1]);
      } else {
        setError(t('agents.error.generic'));
      }
    } finally {
      setLoading(false);
    }
  };

  // Resume from History's "?run=<agent_runs.id>" link. This agent
  // compiles its LangGraph with no checkpointer at all (single-shot,
  // confirmed in agent_runner.py) — there's no session_id/continue
  // concept to restore, only the stored output, so this just re-hydrates
  // citations/domains/query directly from agent_runs.output. Silent
  // fallback on any failure (bad/expired link) rather than an error.
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const stored = await get(`/api/v1/agent-runs/${runId}`);
        const out = (stored.output as Record<string, unknown>) ?? {};
        if (typeof out.query === 'string') setQuery(out.query);
        const restoredCitations = (out.merged_citations ?? out.citations) as Array<Record<string, unknown>> | undefined;
        setCitations(restoredCitations ?? []);
        setDomains((out.detected_domains as string[]) ?? []);
        setHasRun(true);
      } catch {
        /* stale/invalid run id — stays on the fresh intake flow */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const domainLabel = (d: string) => {
    const key = `domain.${d}`;
    const resolved = t(key);
    return resolved === key ? d : resolved;
  };

  return (
    <>
      <AgentPageHeader title={t(agentTitleKey('research-synthesiser'))} />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        <p className="text-sm text-zinc-600 leading-relaxed dark:text-zinc-400">{t('agents.research-synthesiser.desc')}</p>

        {planRequired && (
          <div className="flex flex-col items-center gap-3 py-8 text-center bg-nk-official/5 border border-nk-official/20 rounded-2xl dark:bg-nk-official/10">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {t('agents.error.plan_required').replace('{plan}', planRequired)}
            </p>
            <Link href="/pricing" className="text-sm font-semibold text-nk-official-dim hover:text-nk-official transition-colors">
              {t('nav.pricing')}
            </Link>
          </div>
        )}
        {error && <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">{error}</p>}

        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={3}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('agents.research-synthesiser.query_placeholder')}
          />
          <button
            type="button"
            disabled={loading || !query.trim()}
            onClick={() => void run()}
            className="self-end px-4 py-2 bg-nk-official hover:bg-nk-official-dim hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-blue-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? t('agents.research-synthesiser.synthesising') : t('agents.research-synthesiser.run_button')}
          </button>
        </section>

        {loading && <AgentLoadingSkeleton message={t('agents.research-synthesiser.synthesising')} />}

        {!loading && domains.length > 0 && (
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            {t('agents.research-synthesiser.domains_label')}: {domains.map(domainLabel).join(', ')}
          </p>
        )}
        {!loading && citations.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {citations.map((c, i) => (
              <CitationChip key={i} citation={c as unknown as Citation} index={i + 1} />
            ))}
          </div>
        )}
        {!loading && hasRun && citations.length === 0 && !error && !planRequired && (
          <p className="text-sm text-center py-8 text-zinc-400 dark:text-zinc-500">
            {t('agents.research-synthesiser.no_results')}
          </p>
        )}
      </motion.div>
    </>
  );
}

export default function ResearchSynthesiserPage() {
  return (
    <Suspense>
      <ResearchSynthesiserPageInner />
    </Suspense>
  );
}
