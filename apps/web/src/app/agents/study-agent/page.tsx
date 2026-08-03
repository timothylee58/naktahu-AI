'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { useI18n } from '@/lib/i18n';
import { agentTitleKey } from '@/lib/agents';

const SUBJECTS = ['sejarah', 'matematik', 'sains', 'bm', 'bi'];

export default function StudyAgentPage() {
  const { t } = useI18n();
  const { start, continue: cont } = useAgentApi();
  const [subject, setSubject] = useState('sejarah');
  const [paperText, setPaperText] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const [followUp, setFollowUp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await start('study-agent', { subject, paper_text: paperText, language: 'bm' });
      setSessionId(String(res.session_id));
      setOutput((res.output as Record<string, unknown>) ?? res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'failed');
    } finally {
      setLoading(false);
    }
  };

  const runContinue = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await cont('study-agent', { session_id: sessionId, message: followUp });
      setOutput((res.output as Record<string, unknown>) ?? res);
    } catch {
      setError('continue-failed');
    } finally {
      setLoading(false);
    }
  };

  const explanations = (output?.explanations as Array<Record<string, unknown>>) ?? [];
  const topics = output?.topic_progress as Record<string, number> | undefined;

  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="bg-white/80 backdrop-blur-md supports-[backdrop-filter]:bg-white/70 border-b border-zinc-100 px-4 py-3 flex gap-3 items-center sticky top-0 z-10 dark:bg-[#0A0F1E]/80 dark:border-white/10">
        <Link href="/agents" className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 transition-colors dark:text-blue-400 dark:hover:text-blue-300">
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t('agents.hub.link')}
        </Link>
        <h1 className="font-bold tracking-tight">{t(agentTitleKey('study-agent'))}</h1>
      </header>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        {error && <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">{error}</p>}
        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Subject</label>
          <select
            className="border border-zinc-200 rounded-lg p-2 text-sm bg-transparent transition-colors focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          >
            {SUBJECTS.map((s) => <option key={s} value={s} className="text-zinc-900">{s}</option>)}
          </select>
          <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Paste past-paper text</label>
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm min-h-[120px] bg-transparent transition-colors focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            value={paperText}
            onChange={(e) => setPaperText(e.target.value)}
            placeholder="Soalan 1: ..."
          />
          <button
            type="button"
            disabled={loading || !paperText.trim()}
            onClick={() => void runStart()}
            className="self-end px-4 py-2 bg-blue-600 hover:bg-blue-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-blue-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? 'Analysing…' : 'Extract & explain'}
          </button>
        </section>
        {explanations.length > 0 && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
            <h2 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">Explanations</h2>
            {explanations.map((ex, i) => (
              <div key={i} className="border-b border-zinc-100 pb-3 text-sm last:border-b-0 last:pb-0 dark:border-white/10">
                <p className="font-medium text-zinc-800 dark:text-zinc-200">{String(ex.question)}</p>
                <p className="text-zinc-600 mt-1 leading-relaxed dark:text-zinc-400">{String(ex.explanation)}</p>
              </div>
            ))}
            {topics && (
              <div className="text-xs text-zinc-500 dark:text-zinc-400">Topics: {Object.entries(topics).map(([k, v]) => `${k} (${v})`).join(', ')}</div>
            )}
            <input
              className="border border-zinc-200 rounded-lg p-2 text-sm bg-transparent transition-colors focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
              placeholder="Ask about a question…"
              value={followUp}
              onChange={(e) => setFollowUp(e.target.value)}
            />
            <button type="button" onClick={() => void runContinue()} className="self-end text-sm text-blue-600 hover:text-blue-700 hover:underline transition-colors dark:text-blue-400 dark:hover:text-blue-300">Follow up</button>
          </section>
        )}
      </motion.div>
    </main>
  );
}
