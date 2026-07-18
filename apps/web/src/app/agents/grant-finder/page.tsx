'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { useI18n } from '@/lib/i18n';

const SECTOR_OPTIONS: ChipOption[] = [
  { id: 'technology', label: 'Teknologi', icon: '🖥' },
  { id: 'fnb', label: 'F&B', icon: '🍜' },
  { id: 'manufacturing', label: 'Pembuatan', icon: '🏭' },
  { id: 'retail', label: 'Runcit', icon: '🛒' },
  { id: 'agriculture', label: 'Pertanian', icon: '🌾' },
  { id: 'creative', label: 'Kreatif', icon: '📐' },
  { id: 'healthcare', label: 'Kesihatan', icon: '⚕️' },
  { id: 'education', label: 'Pendidikan', icon: '📚' },
];

const STAGE_OPTIONS: ChipOption[] = [
  { id: 'idea', label: 'Idea', icon: '💡' },
  { id: 'early', label: 'Permulaan', icon: '🌱' },
  { id: 'growth', label: 'Pertumbuhan', icon: '📈' },
  { id: 'established', label: 'Stabil', icon: '🏢' },
];

const FUNDING_OPTIONS: ChipOption[] = [
  { id: 'under_10k', label: '< RM10k' },
  { id: '10k_50k', label: 'RM10k–50k' },
  { id: '50k_200k', label: 'RM50k–200k' },
  { id: 'above_200k', label: '> RM200k' },
];

type Grant = {
  name: string;
  eligibility: string;
  amount_hint: string;
  deadline_hint: string;
  url: string | null;
  match_score?: number;
};

function parseGrant(raw: unknown): Grant | null {
  if (!raw || typeof raw !== 'object') return null;
  const row = raw as Record<string, unknown>;
  const name = typeof row.name === 'string' ? row.name : '';
  if (!name) return null;
  return {
    name,
    eligibility: typeof row.eligibility === 'string' ? row.eligibility : '',
    amount_hint: typeof row.amount_hint === 'string' ? row.amount_hint : '',
    deadline_hint: typeof row.deadline_hint === 'string' ? row.deadline_hint : '',
    url: typeof row.url === 'string' && row.url.length > 0 ? row.url : null,
    match_score: typeof row.match_score === 'number' ? row.match_score : undefined,
  };
}

function parseGrants(raw: unknown): Grant[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(parseGrant).filter((g): g is Grant => g !== null);
}

export default function GrantFinderPage() {
  const { t } = useI18n();
  const { start } = useAgentApi();
  const [sector, setSector] = useState<string[]>([]);
  const [stage, setStage] = useState<string[]>([]);
  const [funding, setFunding] = useState<string[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    setLoading(true);
    setError(null);
    try {
      const fundingLabel = FUNDING_OPTIONS.find((o) => o.id === funding[0])?.label ?? '';
      const res = await start('grant-finder', {
        sector: sector[0] ?? 'technology',
        business_stage: stage[0] ?? 'early',
        funding_need: fundingLabel || 'RM 50,000 working capital',
        language: 'bm',
      });
      const out = (res.output as Record<string, unknown>) ?? res;
      setGrants(parseGrants(out.grants ?? out.recommendations));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Gagal mendapatkan hasil');
    } finally {
      setLoading(false);
    }
  };

  const canSearch = sector.length > 0;

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-white/10 dark:bg-[#0A0F1E]/80">
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-3">
          <Link href="/agents" className="inline-flex items-center gap-1.5 text-sm text-blue-600 transition-colors hover:text-blue-500 dark:text-blue-400">
            <ArrowLeft className="h-4 w-4" aria-hidden />
            Agents
          </Link>
          <span className="text-zinc-300 dark:text-white/20" aria-hidden>/</span>
          <h1 className="text-sm font-bold">Grant Finder</h1>
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-semibold dark:bg-blue-500/15 dark:text-blue-300">Recommended</span>
        </div>
      </header>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Match your profile to Malaysian government grants — MDEC, TEKUN, MARA, Cradle, and more.</p>
        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
          <input className="border border-zinc-200 rounded-lg p-2 text-sm bg-transparent transition-colors focus:outline-none focus:border-blue-400 dark:border-white/10" value={sector} onChange={(e) => setSector(e.target.value)} placeholder="Sector" />
          <input className="border border-zinc-200 rounded-lg p-2 text-sm bg-transparent transition-colors focus:outline-none focus:border-blue-400 dark:border-white/10" value={stage} onChange={(e) => setStage(e.target.value)} placeholder="Stage (early/growth)" />
          <input className="border border-zinc-200 rounded-lg p-2 text-sm bg-transparent transition-colors focus:outline-none focus:border-blue-400 dark:border-white/10" value={need} onChange={(e) => setNeed(e.target.value)} placeholder="Funding need" />
          <button type="button" disabled={loading} onClick={() => void search()} className="self-end px-4 py-2 bg-blue-600 hover:bg-blue-500 transition-colors text-white rounded-xl text-sm font-semibold disabled:opacity-50">
            {loading ? 'Searching…' : 'Find grants'}
          </button>
        </section>
        {grants.length > 0 && (
          <ul className="flex flex-col gap-3">
            {grants.map((g) => (
              <motion.li
                key={g.name}
                whileHover={{ y: -2 }}
                className="bg-white border border-zinc-200 rounded-2xl p-4 text-sm shadow-sm transition-shadow hover:shadow-md dark:bg-white/5 dark:border-white/10"
              >
                <p className="font-semibold">{g.name}</p>
                <p className="text-zinc-600 mt-1 dark:text-zinc-400">{g.eligibility}</p>
                <p className="text-xs text-zinc-500 mt-1 dark:text-zinc-500">
                  {g.amount_hint}
                  {g.amount_hint && g.deadline_hint ? ' · ' : ''}
                  {g.deadline_hint}
                </p>
                {g.url && (
                  <a
                    href={g.url}
                    className="text-blue-600 text-xs mt-2 inline-block dark:text-blue-400"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Mohon sekarang →
                  </a>
                )}
              </motion.li>
            ))}
          </div>
        )}
      </motion.div>
    </main>
  );
}
