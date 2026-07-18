'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
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
    <main className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="bg-white/80 backdrop-blur-md supports-[backdrop-filter]:bg-white/70 border-b border-zinc-100 px-4 py-3 flex gap-3 items-center sticky top-0 z-10 dark:bg-[#0A0F1E]/80 dark:border-white/10">
        <Link href="/agents" className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 transition-colors dark:text-blue-400 dark:hover:text-blue-300">
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Agents
        </Link>
        <h1 className="font-bold tracking-tight">Health Triage</h1>
      </header>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        <p className="text-xs text-zinc-500 leading-relaxed dark:text-zinc-400">Free civic tool — not a medical diagnosis. For emergencies call 999.</p>
        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={4}
            value={symptoms}
            onChange={(e) => setSymptoms(e.target.value)}
            placeholder="Demam, batuk, sakit kepala sejak 2 hari…"
          />
          <button
            type="button"
            disabled={loading || !symptoms.trim()}
            onClick={() => void submit()}
            className="self-end px-4 py-2 bg-red-600 hover:bg-red-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-red-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? 'Checking…' : 'Get guidance'}
          </button>
        </section>
        {output && (
          <section className="bg-white border border-red-100 rounded-2xl p-4 text-sm shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-red-500/30">
            <p className="font-medium">{String(output.facility_recommendation)}</p>
            <ul className="mt-2 space-y-1">{facilities.map((f) => <li key={f.type} className="text-zinc-600 dark:text-zinc-400">{f.name} — {f.action}</li>)}</ul>
            <p className="mt-3 text-xs text-amber-800 dark:text-amber-300">{String(output.disclaimer)}</p>
          </section>
        )}
      </motion.div>
    </main>
  );
}
