'use client';

import { Suspense, useRef, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChatBubbles, type ChatMessage } from '@/components/agents/ChatBubbles';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { CitationChip } from '@/components/chat/CitationChip';
import { PropertyListingSubmitCard } from '@/components/agents/PropertyListingSubmitCard';
import { useI18n } from '@/lib/i18n';
import type { Citation } from '@/lib/types';

// This agent's `language` field is the target language for its guided
// intake, not free-text detection — same precedented pattern as
// retrenchment-navigator/immigration-navigator's localeToApiLanguage.
function localeToApiLanguage(locale: string): 'bm' | 'en' | 'zh' {
  if (locale === 'ms') return 'bm';
  if (locale === 'zh') return 'zh';
  return 'en';
}

type LeadTier = 'hot' | 'warm' | 'cold';

function PropertyConciergePageInner() {
  const { t, locale } = useI18n();
  const { start, continue: cont, get } = useAgentApi();
  const searchParams = useSearchParams();
  const [message, setMessage] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'welcome', role: 'bot', content: t('agents.property-concierge.welcome') },
  ]);
  const [nextPrompt, setNextPrompt] = useState<string | null>(null);
  const [leadTier, setLeadTier] = useState<LeadTier | null>(null);
  const [checklist, setChecklist] = useState<string[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [escalationMessage, setEscalationMessage] = useState<string | null>(null);
  const [citations, setCitations] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Resume from History's "?run=<agent_runs.id>" link — same pattern as
  // retrenchment-navigator: no persisted chat transcript server-side, so
  // this restores the structured result panel + session_id.
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const run = await get(`/api/v1/agent-runs/${runId}`);
        const out = (run.output as Record<string, unknown>) ?? {};
        setSessionId(typeof run.session_id === 'string' ? run.session_id : null);
        if (out.lead_tier) setLeadTier(out.lead_tier as LeadTier);
        if (Array.isArray(out.checklist)) setChecklist(out.checklist as string[]);
        if (Array.isArray(out.warnings)) setWarnings(out.warnings as string[]);
        if (typeof out.escalation_message === 'string') setEscalationMessage(out.escalation_message);
        if (Array.isArray(out.citations)) setCitations(out.citations as Array<Record<string, unknown>>);
        setMessages((prev) => [
          ...prev,
          { id: 'resumed', role: 'bot', content: t('agents.property-concierge.result_ready') },
        ]);
      } catch {
        /* stale/invalid run id — stays on the fresh intake flow */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = async (text?: string) => {
    const msg = text ?? message;
    if (!msg.trim()) return;
    const userMsg: ChatMessage = { id: `u_${Date.now()}`, role: 'user', content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setMessage('');
    setLoading(true);

    try {
      const res = sessionId
        ? await cont('property-concierge', { session_id: sessionId, message: msg })
        : await start('property-concierge', { message: msg, language: localeToApiLanguage(locale) });

      if (!sessionId && res.session_id) setSessionId(String(res.session_id));

      const out = (res.output as Record<string, unknown>) ?? res;
      const botText = String(
        (res.next_prompt as string) ?? (out.next_prompt as string) ?? t('agents.property-concierge.result_ready'),
      );
      const botMsg: ChatMessage = { id: `b_${Date.now()}`, role: 'bot', content: botText };
      setMessages((prev) => [...prev, botMsg]);

      if (out.lead_tier) setLeadTier(out.lead_tier as LeadTier);
      if (Array.isArray(out.checklist)) setChecklist(out.checklist as string[]);
      if (Array.isArray(out.warnings)) setWarnings(out.warnings as string[]);
      if (typeof out.escalation_message === 'string') setEscalationMessage(out.escalation_message);
      if (Array.isArray(out.citations)) setCitations(out.citations as Array<Record<string, unknown>>);
      setNextPrompt((res.next_prompt as string) ?? (out.next_prompt as string) ?? null);
    } catch {
      const errMsg: ChatMessage = { id: `e_${Date.now()}`, role: 'bot', content: t('agents.property-concierge.error') };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  // Client-initiated only — opens the user's own WhatsApp with the brief
  // prefilled and no recipient chosen, so they pick who to send it to.
  // No backend telephony/messaging provider involved (see
  // property_concierge/nodes.py's module docstring for why not).
  const shareViaWhatsApp = () => {
    if (!escalationMessage) return;
    window.open(`https://wa.me/?text=${encodeURIComponent(escalationMessage)}`, '_blank', 'noopener,noreferrer');
  };

  const tierLabel = (tier: LeadTier) => t(`agents.property-concierge.tier.${tier}`);
  const tierClass: Record<LeadTier, string> = {
    hot: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-500/30',
    warm: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-500/30',
    cold: 'bg-zinc-50 text-zinc-600 border-zinc-200 dark:bg-white/5 dark:text-zinc-400 dark:border-white/10',
  };

  return (
    <>
      <AgentPageHeader title={t('agents.property-concierge.title')} />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        {(leadTier || checklist.length > 0 || citations.length > 0) && (
          <section className="flex flex-col gap-3">
            {leadTier && (
              <div className={`rounded-2xl border p-4 flex items-center justify-between gap-3 ${tierClass[leadTier]}`}>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide opacity-80">
                    {t('agents.property-concierge.section.tier')}
                  </p>
                  <p className="text-lg font-bold mt-0.5">{tierLabel(leadTier)}</p>
                </div>
                {escalationMessage && (
                  <button
                    type="button"
                    onClick={shareViaWhatsApp}
                    className="flex-shrink-0 px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-xl text-xs font-semibold transition-colors"
                  >
                    {t('agents.property-concierge.share_whatsapp')}
                  </button>
                )}
              </div>
            )}

            {checklist.length > 0 && (
              <div className="bg-white border border-zinc-200 rounded-xl p-4 dark:bg-white/5 dark:border-white/10">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500 mb-2">
                  {t('agents.property-concierge.section.checklist')}
                </p>
                <ul className="flex flex-col gap-2">
                  {checklist.map((c) => (
                    <li key={c} className="flex items-start gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" className="w-4 h-4 mt-0.5 flex-shrink-0 text-lime-600 dark:text-lime-400" aria-hidden>
                        <rect x="1.5" y="1.5" width="13" height="13" rx="3" stroke="currentColor" strokeWidth="1.3" />
                      </svg>
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {warnings.length > 0 && (
              <div className="text-xs text-amber-800 bg-amber-50 border border-amber-100 p-3 rounded-xl space-y-1 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
                {warnings.map((w) => <p key={w}>{w}</p>)}
              </div>
            )}

            {citations.length > 0 && (
              <div className="flex flex-col gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                  {t('agents.property-concierge.section.sources')}
                </p>
                <div className="flex flex-wrap gap-2">
                  {citations.map((c, i) => (
                    <CitationChip key={i} citation={c as unknown as Citation} index={i + 1} />
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        <PropertyListingSubmitCard />

        <ChatBubbles messages={messages} />
        {loading && <AgentLoadingSkeleton message={t('agents.property-concierge.thinking')} />}
        <div ref={bottomRef} />

        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-2 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          {nextPrompt && <p className="text-sm text-nk-official-dim dark:text-nk-official">{nextPrompt}</p>}
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-lime-500/50 focus:outline-none focus:ring-1 focus:ring-lime-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t('agents.property-concierge.placeholder')}
          />
          <button
            type="button"
            disabled={loading || !message.trim()}
            onClick={() => void send()}
            className="self-end px-4 py-2 bg-lime-600 hover:bg-lime-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-lime-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading
              ? t('agents.property-concierge.thinking')
              : sessionId
                ? t('agents.property-concierge.button.continue')
                : t('agents.property-concierge.button.start')}
          </button>
        </section>
      </motion.div>
    </>
  );
}

export default function PropertyConciergePage() {
  return (
    <Suspense>
      <PropertyConciergePageInner />
    </Suspense>
  );
}
