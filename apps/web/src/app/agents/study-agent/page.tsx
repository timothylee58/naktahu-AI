'use client';

import { useState } from 'react';
import Link from 'next/link';
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
    <main className="min-h-screen bg-zinc-50">
      <header className="bg-white border-b px-4 py-3 flex gap-3 items-center">
        <Link href="/agents" className="text-sm text-blue-600">← Agents</Link>
        <h1 className="font-bold">Study Agent</h1>
      </header>
      <div className="max-w-2xl mx-auto p-4 flex flex-col gap-4">
        {error && <p className="text-sm text-red-600">{error}</p>}
        <section className="bg-white border rounded-2xl p-4 flex flex-col gap-3">
          <label className="text-sm font-medium">Subject</label>
          <select className="border rounded-lg p-2 text-sm" value={subject} onChange={(e) => setSubject(e.target.value)}>
            {SUBJECTS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <label className="text-sm font-medium">Paste past-paper text</label>
          <textarea className="border rounded-xl p-3 text-sm min-h-[120px]" value={paperText} onChange={(e) => setPaperText(e.target.value)} placeholder="Soalan 1: ..." />
          <button type="button" disabled={loading || !paperText.trim()} onClick={() => void runStart()} className="self-end px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold disabled:opacity-50">
            {loading ? 'Analysing…' : 'Extract & explain'}
          </button>
        </section>
        {explanations.length > 0 && (
          <section className="bg-white border rounded-2xl p-4 flex flex-col gap-3">
            <h2 className="font-semibold text-sm">Explanations</h2>
            {explanations.map((ex, i) => (
              <div key={i} className="border-b pb-3 text-sm">
                <p className="font-medium text-zinc-800">{String(ex.question)}</p>
                <p className="text-zinc-600 mt-1">{String(ex.explanation)}</p>
              </div>
            ))}
            {topics && (
              <div className="text-xs text-zinc-500">Topics: {Object.entries(topics).map(([k, v]) => `${k} (${v})`).join(', ')}</div>
            )}
            <input className="border rounded-lg p-2 text-sm" placeholder="Ask about a question…" value={followUp} onChange={(e) => setFollowUp(e.target.value)} />
            <button type="button" onClick={() => void runContinue()} className="self-end text-sm text-blue-600">Follow up</button>
          </section>
        )}
      </div>
    </main>
  );
}
