'use client';

import { useRef, useState, useEffect } from 'react';
import Link from 'next/link';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChatBubbles, QuickReplies, type ChatMessage } from '@/components/agents/ChatBubbles';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { useI18n } from '@/lib/i18n';

const INITIAL_QUICK_REPLIES = [
  'I want to work in Malaysia',
  'Student visa for university',
  'Visit family for 3 months',
  'Start a business in KL',
  'Extend my current visa',
];


export default function ImmigrationNavigatorPage() {
  const { t } = useI18n();
  const { start, continue: cont } = useAgentApi();
  const [message, setMessage] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'welcome', role: 'bot', content: 'Selamat datang! Saya boleh bantu anda dengan maklumat visa dan imigresen Malaysia. Dari mana anda berasal, dan jenis visa apa yang anda perlukan?' },
  ]);
  const [nextPrompt, setNextPrompt] = useState<string | null>(null);
  const [quickReplies, setQuickReplies] = useState<string[]>(INITIAL_QUICK_REPLIES);
  const [checklist, setChecklist] = useState<string[]>([]);
  const [visaType, setVisaType] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);


  const send = async (text?: string) => {
    const msg = text ?? message;
    if (!msg.trim()) return;
    const userMsg: ChatMessage = { id: `u_${Date.now()}`, role: 'user', content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setMessage('');
    setQuickReplies([]);
    setLoading(true);

    try {
      const res = sessionId
        ? await cont('immigration-navigator', { session_id: sessionId, message: msg })
        : await start('immigration-navigator', { message: msg, language: 'bm' });

      if (!sessionId && res.session_id) setSessionId(String(res.session_id));

      const out = (res.output as Record<string, unknown>) ?? res;
      const botText = String(out.response ?? out.summary ?? out.output ?? JSON.stringify(out));
      const botMsg: ChatMessage = { id: `b_${Date.now()}`, role: 'bot', content: botText };
      setMessages((prev) => [...prev, botMsg]);

      // Extract structured data
      if (out.visa_type) setVisaType(String(out.visa_type));
      if (Array.isArray(out.checklist)) setChecklist(out.checklist as string[]);
      if (Array.isArray(out.warnings)) setWarnings(out.warnings as string[]);
      setNextPrompt((res.next_prompt as string) ?? (out.next_prompt as string) ?? null);

      // Generate contextual quick replies
      if (res.next_prompt || out.next_prompt) {
        setQuickReplies(['Yes', 'No', 'I need more details', 'What documents do I need?']);
      } else {
        setQuickReplies([]);
      }
    } catch {
      const errMsg: ChatMessage = { id: `e_${Date.now()}`, role: 'bot', content: 'Maaf, ralat berlaku. Sila cuba lagi.' };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };


  return (
    <main className="flex min-h-screen flex-col bg-zinc-50">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/90 backdrop-blur px-4 py-3 flex gap-3 items-center">
        <Link href="/agents" className="text-sm text-blue-600 hover:underline">← Agents</Link>
        <h1 className="font-bold text-zinc-900">Immigration Navigator</h1>
        <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">1 kredit</span>
      </header>

      <div className="flex flex-1 flex-col max-w-2xl mx-auto w-full p-4 gap-4">
        {/* Visa summary card (appears after intake) */}
        {visaType && (
          <section className="rounded-2xl border border-teal-200 bg-teal-50 p-5 flex flex-col gap-3">
            <h2 className="text-sm font-bold text-teal-800 flex items-center gap-2">
              <span aria-hidden>🟢</span> {visaType}
            </h2>
            {checklist.length > 0 && (
              <ul className="space-y-2">
                {checklist.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-zinc-700">
                    <span className="mt-0.5 text-teal-600">✅</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            )}
            {warnings.length > 0 && (
              <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                {warnings.map((w, i) => (
                  <p key={i} className="text-xs text-amber-800 flex items-start gap-1.5">
                    <span>⚠️</span> {w}
                  </p>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Chat messages */}
        <div className="flex-1 overflow-y-auto">
          <ChatBubbles messages={messages} />
          {loading && (
            <div className="mt-3">
              <AgentLoadingSkeleton message="Menjawab…" />
            </div>
          )}
          <div ref={bottomRef} />
        </div>


        {/* Quick replies */}
        {quickReplies.length > 0 && !loading && (
          <QuickReplies options={quickReplies} onSelect={(opt) => void send(opt)} />
        )}

        {/* Next prompt hint */}
        {nextPrompt && !loading && (
          <p className="text-xs text-blue-600 font-medium px-1">{nextPrompt}</p>
        )}

        {/* Input area */}
        <div className="sticky bottom-0 rounded-2xl border border-zinc-200 bg-white p-3 flex gap-2">
          <textarea
            className="flex-1 resize-none rounded-xl border-0 p-2 text-sm placeholder:text-zinc-400 focus:outline-none"
            rows={1}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            placeholder="Taip mesej anda…"
          />
          <button
            type="button"
            disabled={loading || !message.trim()}
            onClick={() => void send()}
            className="flex-shrink-0 rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-50"
          >
            {loading ? '…' : '→'}
          </button>
        </div>
      </div>
    </main>
  );
}
