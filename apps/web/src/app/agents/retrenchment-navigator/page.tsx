'use client';

import { useRef, useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChatBubbles, type ChatMessage } from '@/components/agents/ChatBubbles';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { useI18n } from '@/lib/i18n';

interface StatutoryBenefits {
  days_per_year_of_service?: number;
  total_days_owed?: number;
  estimated_benefit_myr?: number;
  basis?: string;
}

interface EisEligibility {
  likely_eligible?: boolean | null;
  note?: string;
}

export default function RetrenchmentNavigatorPage() {
  const { t } = useI18n();
  const { start, continue: cont } = useAgentApi();
  const [message, setMessage] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'welcome', role: 'bot', content: t('agents.retrenchment-navigator.welcome') },
  ]);
  const [nextPrompt, setNextPrompt] = useState<string | null>(null);
  const [statutoryBenefits, setStatutoryBenefits] = useState<StatutoryBenefits | null>(null);
  const [eisEligibility, setEisEligibility] = useState<EisEligibility | null>(null);
  const [noticePeriodStatus, setNoticePeriodStatus] = useState<string | null>(null);
  const [checklist, setChecklist] = useState<string[]>([]);
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
    setLoading(true);

    try {
      const res = sessionId
        ? await cont('retrenchment-navigator', { session_id: sessionId, message: msg })
        : await start('retrenchment-navigator', { message: msg, language: 'bm' });

      if (!sessionId && res.session_id) setSessionId(String(res.session_id));

      const out = (res.output as Record<string, unknown>) ?? res;
      const botText = String(
        (res.next_prompt as string) ?? (out.next_prompt as string) ?? t('agents.retrenchment-navigator.result_ready'),
      );
      const botMsg: ChatMessage = { id: `b_${Date.now()}`, role: 'bot', content: botText };
      setMessages((prev) => [...prev, botMsg]);

      if (out.statutory_benefits) setStatutoryBenefits(out.statutory_benefits as StatutoryBenefits);
      if (out.eis_eligibility) setEisEligibility(out.eis_eligibility as EisEligibility);
      if (out.notice_period_status) setNoticePeriodStatus(String(out.notice_period_status));
      if (Array.isArray(out.checklist)) setChecklist(out.checklist as string[]);
      if (Array.isArray(out.warnings)) setWarnings(out.warnings as string[]);
      setNextPrompt((res.next_prompt as string) ?? (out.next_prompt as string) ?? null);
    } catch {
      const errMsg: ChatMessage = { id: `e_${Date.now()}`, role: 'bot', content: t('agents.retrenchment-navigator.error') };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <AgentPageHeader title={t('agents.retrenchment-navigator.title')} />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        {(statutoryBenefits || eisEligibility || noticePeriodStatus) && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10 flex flex-col gap-3">
            {statutoryBenefits?.estimated_benefit_myr != null && (
              <div>
                <h2 className="font-semibold text-teal-800 dark:text-teal-300">{t('agents.retrenchment-navigator.section.benefits')}</h2>
                <p className="text-lg font-bold mt-1">RM {statutoryBenefits.estimated_benefit_myr.toLocaleString()}</p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">{statutoryBenefits.basis}</p>
              </div>
            )}
            {eisEligibility && (
              <div>
                <h2 className="font-semibold text-teal-800 dark:text-teal-300">{t('agents.retrenchment-navigator.section.eis')}</h2>
                <p className="text-sm mt-1">
                  {eisEligibility.likely_eligible === true
                    ? t('agents.retrenchment-navigator.eis.likely')
                    : eisEligibility.likely_eligible === false
                      ? t('agents.retrenchment-navigator.eis.unlikely')
                      : t('agents.retrenchment-navigator.eis.unknown')}
                </p>
                {eisEligibility.note && <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">{eisEligibility.note}</p>}
              </div>
            )}
            {noticePeriodStatus && noticePeriodStatus !== 'unknown' && (
              <div>
                <h2 className="font-semibold text-teal-800 dark:text-teal-300">{t('agents.retrenchment-navigator.section.notice')}</h2>
                <p className="text-sm mt-1">
                  {noticePeriodStatus === 'sufficient'
                    ? t('agents.retrenchment-navigator.notice.sufficient')
                    : t('agents.retrenchment-navigator.notice.owed')}
                </p>
              </div>
            )}
            {checklist.length > 0 && (
              <div>
                <h2 className="font-semibold text-teal-800 dark:text-teal-300">{t('agents.retrenchment-navigator.section.checklist')}</h2>
                <ul className="mt-1 text-sm list-disc pl-5 space-y-1 text-zinc-700 dark:text-zinc-300">
                  {checklist.map((c) => <li key={c}>{c}</li>)}
                </ul>
              </div>
            )}
            {warnings.length > 0 && (
              <div className="text-xs text-amber-800 bg-amber-50 border border-amber-100 p-2 rounded-lg space-y-1 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
                {warnings.map((w) => <p key={w}>{w}</p>)}
              </div>
            )}
          </section>
        )}

        <ChatBubbles messages={messages} />
        <div ref={bottomRef} />

        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-2 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          {nextPrompt && <p className="text-sm text-blue-700 dark:text-blue-400">{nextPrompt}</p>}
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-teal-500/50 focus:outline-none focus:ring-1 focus:ring-teal-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t('agents.retrenchment-navigator.placeholder')}
          />
          <button
            type="button"
            disabled={loading}
            onClick={() => void send()}
            className="self-end px-4 py-2 bg-teal-600 hover:bg-teal-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-teal-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? '…' : sessionId ? t('agents.retrenchment-navigator.button.continue') : t('agents.retrenchment-navigator.button.start')}
          </button>
        </section>
      </motion.div>
    </>
  );
}
