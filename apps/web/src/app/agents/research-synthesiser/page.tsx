'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';

export default function ResearchSynthesiserPage() {
  const { start } = useAgentApi();
  const [query, setQuery] = useState('');
  const [citations, setCitations] = useState<Array<Record<string, unknown>>>([]);
  const [domains, setDomains] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await start('research-synthesiser', { query, language: 'bm' });
      setCitations((res.citations as Array<Record<string, unknown>>) ?? []);
      setDomains((res.detected_domains as string[]) ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'requires-business-plan');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <AgentPageHeader title="Research Synthesiser" />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        <p className="text-sm text-zinc-600 leading-relaxed dark:text-zinc-400">Parallel fan-out across 3 RAG domains — Business / API Growth tier.</p>
        {error && <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">{error}</p>}
        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-purple-500/50 focus:outline-none focus:ring-1 focus:ring-purple-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={3}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Compare EPF withdrawal rules and tax implications for retirees…"
          />
          <button
            type="button"
            disabled={loading || !query.trim()}
            onClick={() => void run()}
            className="self-end px-4 py-2 bg-purple-600 hover:bg-purple-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-purple-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? 'Synthesising…' : 'Run parallel RAG'}
          </button>
        </section>
        {domains.length > 0 && <p className="text-xs text-zinc-500 dark:text-zinc-400">Domains: {domains.join(', ')}</p>}
        {citations.length > 0 && (
          <ul className="flex flex-col gap-2">
            {citations.map((c, i) => (
              <motion.li key={i} whileHover={{ y: -2 }} className="bg-white border border-zinc-200 rounded-xl p-3 text-sm shadow-sm transition-shadow hover:shadow-md dark:bg-white/5 dark:border-white/10">
                <a href={String(c.url)} className="font-medium text-blue-700 hover:underline dark:text-blue-400" target="_blank" rel="noreferrer">{String(c.title)}</a>
                <span className="text-xs text-zinc-500 ml-2 dark:text-zinc-500">{String(c.ministry)}</span>
              </motion.li>
            ))}
          </ul>
        )}
      </motion.div>
    </>
  );
}
