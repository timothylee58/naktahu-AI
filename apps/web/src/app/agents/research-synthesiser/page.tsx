'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAgentApi } from '@/lib/hooks/useAgentApi';

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
    <main className="min-h-screen bg-zinc-50">
      <header className="bg-white border-b px-4 py-3 flex gap-3 items-center">
        <Link href="/agents" className="text-sm text-blue-600">← Agents</Link>
        <h1 className="font-bold">Research Synthesiser</h1>
      </header>
      <div className="max-w-2xl mx-auto p-4 flex flex-col gap-4">
        <p className="text-sm text-zinc-600">Parallel fan-out across 3 RAG domains — Business / API Growth tier.</p>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <section className="bg-white border rounded-2xl p-4 flex flex-col gap-3">
          <textarea className="border rounded-xl p-3 text-sm" rows={3} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Compare EPF withdrawal rules and tax implications for retirees…" />
          <button type="button" disabled={loading || !query.trim()} onClick={() => void run()} className="self-end px-4 py-2 bg-purple-600 text-white rounded-xl text-sm font-semibold disabled:opacity-50">
            {loading ? 'Synthesising…' : 'Run parallel RAG'}
          </button>
        </section>
        {domains.length > 0 && <p className="text-xs text-zinc-500">Domains: {domains.join(', ')}</p>}
        {citations.length > 0 && (
          <ul className="flex flex-col gap-2">
            {citations.map((c, i) => (
              <li key={i} className="bg-white border rounded-xl p-3 text-sm">
                <a href={String(c.url)} className="font-medium text-blue-700" target="_blank" rel="noreferrer">{String(c.title)}</a>
                <span className="text-xs text-zinc-500 ml-2">{String(c.ministry)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
