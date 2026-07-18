'use client';

import { useState } from 'react';
import Link from 'next/link';
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
    <main className="min-h-screen bg-zinc-50">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/90 backdrop-blur px-4 py-3 flex gap-3 items-center">
        <Link href="/agents" className="text-sm text-blue-600 hover:underline">← Agents</Link>
        <h1 className="font-bold text-zinc-900">Grant Finder</h1>
        <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">Percuma</span>
      </header>

      <div className="max-w-2xl mx-auto p-4 flex flex-col gap-5">
        <p className="text-sm text-zinc-600 leading-relaxed">
          Padankan profil perniagaan anda dengan geran kerajaan Malaysia — MDEC, TEKUN, MARA, Cradle, dan banyak lagi.
        </p>

        {/* Sector selector */}
        <section className="rounded-2xl border border-zinc-200 bg-white p-5 flex flex-col gap-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">Sektor perniagaan</h2>
            <p className="text-xs text-zinc-500 mt-0.5">Pilih sektor utama anda</p>
          </div>
          <ChipSelector
            options={SECTOR_OPTIONS}
            selected={sector}
            onToggle={(id) => setSector([id])}
            multiple={false}
          />
        </section>

        {/* Stage selector */}
        {sector.length > 0 && (
          <section className="rounded-2xl border border-zinc-200 bg-white p-5 flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-zinc-900">Peringkat perniagaan</h2>
            <ChipSelector
              options={STAGE_OPTIONS}
              selected={stage}
              onToggle={(id) => setStage([id])}
              multiple={false}
            />
          </section>
        )}

        {/* Funding need */}
        {stage.length > 0 && (
          <section className="rounded-2xl border border-zinc-200 bg-white p-5 flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-zinc-900">Jumlah dana diperlukan</h2>
            <ChipSelector
              options={FUNDING_OPTIONS}
              selected={funding}
              onToggle={(id) => setFunding([id])}
              multiple={false}
              size="sm"
            />
            <button
              type="button"
              disabled={loading || !canSearch}
              onClick={() => void search()}
              className="self-end mt-2 px-5 py-2.5 bg-emerald-600 text-white rounded-xl text-sm font-semibold disabled:opacity-50 transition-colors hover:bg-emerald-700"
            >
              {loading ? 'Mencari…' : 'Cari geran'}
            </button>
          </section>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && <AgentLoadingSkeleton message="Memadankan profil anda dengan geran…" />}

        {/* Results */}
        {grants.length > 0 && !loading && (
          <div className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-zinc-900">
              {grants.length} geran dijumpai
            </h2>
            {grants.map((g, i) => (
              <div
                key={g.name}
                className="rounded-2xl border border-zinc-200 bg-white p-5 flex flex-col gap-3 transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
                      <span className="text-base" aria-hidden>🏛</span>
                    </div>
                    <h3 className="text-sm font-semibold text-zinc-900">{g.name}</h3>
                  </div>
                  {g.match_score != null && (
                    <span className="flex-shrink-0 rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700">
                      {Math.round(g.match_score * 100)}% padanan
                    </span>
                  )}
                </div>

                {g.amount_hint && (
                  <p className="text-lg font-bold text-emerald-700">{g.amount_hint}</p>
                )}

                {g.eligibility && (
                  <div className="flex items-start gap-2">
                    <span className="text-xs mt-0.5">✅</span>
                    <p className="text-sm text-zinc-600">{g.eligibility}</p>
                  </div>
                )}

                {g.deadline_hint && (
                  <div className="flex items-start gap-2">
                    <span className="text-xs mt-0.5">📅</span>
                    <p className="text-xs text-zinc-500">{g.deadline_hint}</p>
                  </div>
                )}

                {g.url && (
                  <a
                    href={g.url}
                    className="mt-1 inline-flex items-center gap-1 text-sm font-semibold text-blue-600 hover:underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Mohon sekarang →
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
