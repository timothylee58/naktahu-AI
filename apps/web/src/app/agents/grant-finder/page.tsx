'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAgentApi } from '@/lib/hooks/useAgentApi';

type Grant = {
  name: string;
  eligibility: string;
  amount_hint: string;
  deadline_hint: string;
  url: string | null;
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
  };
}

function parseGrants(raw: unknown): Grant[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(parseGrant).filter((g): g is Grant => g !== null);
}

export default function GrantFinderPage() {
  const { start } = useAgentApi();
  const [sector, setSector] = useState('technology');
  const [stage, setStage] = useState('early');
  const [need, setNeed] = useState('RM 50,000 working capital');
  const [grants, setGrants] = useState<Grant[]>([]);
  const [loading, setLoading] = useState(false);

  const search = async () => {
    setLoading(true);
    try {
      const res = await start('grant-finder', {
        sector,
        business_stage: stage,
        funding_need: need,
        language: 'bm',
      });
      const out = (res.output as Record<string, unknown>) ?? res;
      setGrants(parseGrants(out.grants));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-zinc-50">
      <header className="bg-white border-b px-4 py-3 flex gap-3 items-center">
        <Link href="/agents" className="text-sm text-blue-600">← Agents</Link>
        <h1 className="font-bold">Grant Finder</h1>
        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-semibold">Recommended</span>
      </header>
      <div className="max-w-2xl mx-auto p-4 flex flex-col gap-4">
        <p className="text-sm text-zinc-600">Match your profile to Malaysian government grants — MDEC, TEKUN, MARA, Cradle, and more.</p>
        <section className="bg-white border rounded-2xl p-4 flex flex-col gap-3">
          <input className="border rounded-lg p-2 text-sm" value={sector} onChange={(e) => setSector(e.target.value)} placeholder="Sector" />
          <input className="border rounded-lg p-2 text-sm" value={stage} onChange={(e) => setStage(e.target.value)} placeholder="Stage (early/growth)" />
          <input className="border rounded-lg p-2 text-sm" value={need} onChange={(e) => setNeed(e.target.value)} placeholder="Funding need" />
          <button type="button" disabled={loading} onClick={() => void search()} className="self-end px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold">
            {loading ? 'Searching…' : 'Find grants'}
          </button>
        </section>
        {grants.length > 0 && (
          <ul className="flex flex-col gap-3">
            {grants.map((g) => (
              <li key={g.name} className="bg-white border rounded-2xl p-4 text-sm">
                <p className="font-semibold">{g.name}</p>
                <p className="text-zinc-600 mt-1">{g.eligibility}</p>
                <p className="text-xs text-zinc-500 mt-1">
                  {g.amount_hint}
                  {g.amount_hint && g.deadline_hint ? ' · ' : ''}
                  {g.deadline_hint}
                </p>
                {g.url && (
                  <a
                    href={g.url}
                    className="text-blue-600 text-xs mt-2 inline-block"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Official source
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
