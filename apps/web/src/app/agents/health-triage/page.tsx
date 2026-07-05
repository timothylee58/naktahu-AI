'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAgentApi } from '@/lib/hooks/useAgentApi';

export default function HealthTriagePage() {
  const { start } = useAgentApi();
  const [symptoms, setSymptoms] = useState('');
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      const res = await start('health-triage', { message: symptoms, language: 'bm' });
      setOutput((res.output as Record<string, unknown>) ?? res);
    } finally {
      setLoading(false);
    }
  };

  const facilities = (output?.facilities as Array<Record<string, string>>) ?? [];

  return (
    <main className="min-h-screen bg-zinc-50">
      <header className="bg-white border-b px-4 py-3 flex gap-3 items-center">
        <Link href="/agents" className="text-sm text-blue-600">← Agents</Link>
        <h1 className="font-bold">Health Triage</h1>
      </header>
      <div className="max-w-2xl mx-auto p-4 flex flex-col gap-4">
        <p className="text-xs text-zinc-500">Free civic tool — not a medical diagnosis. For emergencies call 999.</p>
        <section className="bg-white border rounded-2xl p-4 flex flex-col gap-3">
          <textarea className="border rounded-xl p-3 text-sm" rows={4} value={symptoms} onChange={(e) => setSymptoms(e.target.value)} placeholder="Demam, batuk, sakit kepala sejak 2 hari…" />
          <button type="button" disabled={loading || !symptoms.trim()} onClick={() => void submit()} className="self-end px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-semibold disabled:opacity-50">
            {loading ? 'Checking…' : 'Get guidance'}
          </button>
        </section>
        {output && (
          <section className="bg-white border border-red-100 rounded-2xl p-4 text-sm">
            <p className="font-medium text-zinc-900">{String(output.facility_recommendation)}</p>
            <ul className="mt-2 space-y-1">{facilities.map((f) => <li key={f.type} className="text-zinc-600">{f.name} — {f.action}</li>)}</ul>
            <p className="mt-3 text-xs text-amber-800">{String(output.disclaimer)}</p>
          </section>
        )}
      </div>
    </main>
  );
}
