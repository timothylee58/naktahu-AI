'use client';

import { useState } from 'react';
import Link from 'next/link';
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
    <main className="min-h-screen bg-zinc-50">
      <header className="bg-white border-b px-4 py-3 flex gap-3 items-center">
        <Link href="/agents" className="text-sm text-blue-600">← Agents</Link>
        <h1 className="font-bold">Immigration Navigator</h1>
      </header>
      <div className="max-w-2xl mx-auto p-4 flex flex-col gap-4">
        {output?.visa_type != null && (
          <section className="bg-white border rounded-2xl p-4">
            <h2 className="font-semibold text-teal-800">{String(output.visa_type)}</h2>
            <ul className="mt-2 text-sm list-disc pl-5">{checklist.map((c) => <li key={c}>{c}</li>)}</ul>
            {warnings.length > 0 && (
              <div className="mt-3 text-xs text-amber-800 bg-amber-50 p-2 rounded-lg">
                {warnings.map((w) => <p key={w}>{w}</p>)}
              </div>
            )}
          </section>
        )}
        <section className="bg-white border rounded-2xl p-4 flex flex-col gap-2">
          {nextPrompt && <p className="text-sm text-blue-700">{nextPrompt}</p>}
          <textarea className="border rounded-xl p-3 text-sm" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} placeholder="I'm from India, want to work in KL for 2 years…" />
          <button type="button" disabled={loading} onClick={() => void send()} className="self-end px-4 py-2 bg-teal-600 text-white rounded-xl text-sm font-semibold">
            {loading ? '…' : sessionId ? 'Continue' : 'Start intake'}
          </button>
        </section>
      </div>
    </main>
  );
}
