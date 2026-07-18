'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';

export default function ImmigrationNavigatorPage() {
  const { start, continue: cont } = useAgentApi();
  const [message, setMessage] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const [nextPrompt, setNextPrompt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!message.trim()) return;
    setLoading(true);
    try {
      const res = sessionId
        ? await cont('immigration-navigator', { session_id: sessionId, message })
        : await start('immigration-navigator', { message, language: 'bm' });
      if (!sessionId) setSessionId(String(res.session_id));
      setOutput((res.output as Record<string, unknown>) ?? res);
      setNextPrompt((res.next_prompt as string) ?? null);
      setMessage('');
    } finally {
      setLoading(false);
    }
  };

  const checklist = (output?.checklist as string[]) ?? [];
  const warnings = (output?.warnings as string[]) ?? [];

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="bg-white/80 backdrop-blur-md supports-[backdrop-filter]:bg-white/70 border-b border-zinc-100 px-4 py-3 flex gap-3 items-center sticky top-0 z-10 dark:bg-[#0A0F1E]/80 dark:border-white/10">
        <Link href="/agents" className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 transition-colors dark:text-blue-400 dark:hover:text-blue-300">
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Agents
        </Link>
        <h1 className="font-bold tracking-tight">Immigration Navigator</h1>
      </header>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        {output?.visa_type != null && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
            <h2 className="font-semibold text-teal-800 dark:text-teal-300">{String(output.visa_type)}</h2>
            <ul className="mt-2 text-sm list-disc pl-5 space-y-1 text-zinc-700 dark:text-zinc-300">{checklist.map((c) => <li key={c}>{c}</li>)}</ul>
            {warnings.length > 0 && (
              <div className="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-100 p-2 rounded-lg space-y-1 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
                {warnings.map((w) => <p key={w}>{w}</p>)}
              </div>
            )}
          </section>
        )}
        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-2 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          {nextPrompt && <p className="text-sm text-blue-700 dark:text-blue-400">{nextPrompt}</p>}
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-teal-500/50 focus:outline-none focus:ring-1 focus:ring-teal-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="I'm from India, want to work in KL for 2 years…"
          />
          <button
            type="button"
            disabled={loading}
            onClick={() => void send()}
            className="self-end px-4 py-2 bg-teal-600 hover:bg-teal-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-teal-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? '…' : sessionId ? 'Continue' : 'Start intake'}
          </button>
        </section>
      </motion.div>
    </main>
  );
}
