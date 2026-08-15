'use client';

import { Suspense, useRef, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChatBubbles, type ChatMessage } from '@/components/agents/ChatBubbles';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { useI18n } from '@/lib/i18n';

// This agent's `language` field is the target language for its guided
// intake, not free-text detection — deriving it from the active UI locale
// instead of hardcoding 'bm' follows the same precedented pattern already
// used by grant-draft-generator/sme-compliance-navigator's `queryLanguage`.
function localeToApiLanguage(locale: string): 'bm' | 'en' | 'zh' {
  if (locale === 'ms') return 'bm';
  if (locale === 'zh') return 'zh';
  return 'en';
}

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

function RetrenchmentNavigatorPageInner() {
  const { t, locale } = useI18n();
  const { start, continue: cont, get } = useAgentApi();
  const searchParams = useSearchParams();
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

  // Resume from History's "?run=<agent_runs.id>" link. No persisted chat
  // transcript server-side (only the latest structured output), so this
  // restores the structured summary panel + session_id (so a follow-up
  // message continues the real thread) and adds one synthetic bot message
  // rather than replaying every prior turn. Silent fallback to a fresh
  // start on any failure (bad/expired link) rather than an error.
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const run = await get(`/api/v1/agent-runs/${runId}`);
        const out = (run.output as Record<string, unknown>) ?? {};
        setSessionId(typeof run.session_id === 'string' ? run.session_id : null);
        if (out.statutory_benefits) setStatutoryBenefits(out.statutory_benefits as StatutoryBenefits);
        if (out.eis_eligibility) setEisEligibility(out.eis_eligibility as EisEligibility);
        if (out.notice_period_status) setNoticePeriodStatus(String(out.notice_period_status));
        if (Array.isArray(out.checklist)) setChecklist(out.checklist as string[]);
        if (Array.isArray(out.warnings)) setWarnings(out.warnings as string[]);
        setMessages((prev) => [
          ...prev,
          { id: 'resumed', role: 'bot', content: t('agents.retrenchment-navigator.result_ready') },
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
        ? await cont('retrenchment-navigator', { session_id: sessionId, message: msg })
        : await start('retrenchment-navigator', { message: msg, language: localeToApiLanguage(locale) });

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
          <section className="flex flex-col gap-3">
            {/* Hero stat — the one number the user came here for gets its
                own visual weight instead of sitting in the same h2 style as
                secondary details like the checklist. Tabular nums so the
                figure doesn't jitter as digits stream in turn by turn. */}
            {statutoryBenefits?.estimated_benefit_myr != null && (
              <div className="bg-teal-50 border border-teal-200 rounded-2xl p-5 dark:bg-teal-500/10 dark:border-teal-500/30">
                <p className="text-xs font-semibold uppercase tracking-wide text-teal-700 dark:text-teal-300">
                  {t('agents.retrenchment-navigator.section.benefits')}
                </p>
                <p className="text-3xl font-bold tracking-tight mt-1 font-mono [font-variant-numeric:tabular-nums] text-teal-900 dark:text-teal-100">
                  RM {statutoryBenefits.estimated_benefit_myr.toLocaleString()}
                </p>
                {statutoryBenefits.basis && (
                  <p className="text-xs text-teal-700/80 dark:text-teal-300/80 mt-1.5">{statutoryBenefits.basis}</p>
                )}
              </div>
            )}

            {/* Status chips — EIS eligibility and notice-period status are
                each a single state, not paragraphs; a 2-up glance-able grid
                reads faster than two stacked prose blocks did. */}
            {(eisEligibility || (noticePeriodStatus && noticePeriodStatus !== 'unknown')) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {eisEligibility && (
                  <div className="bg-white border border-zinc-200 rounded-xl p-3.5 dark:bg-white/5 dark:border-white/10">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                      {t('agents.retrenchment-navigator.section.eis')}
                    </p>
                    <p
                      className={`text-sm font-medium mt-1 ${
                        eisEligibility.likely_eligible === true
                          ? 'text-green-700 dark:text-green-400'
                          : eisEligibility.likely_eligible === false
                            ? 'text-zinc-600 dark:text-zinc-400'
                            : 'text-amber-700 dark:text-amber-400'
                      }`}
                    >
                      {eisEligibility.likely_eligible === true
                        ? t('agents.retrenchment-navigator.eis.likely')
                        : eisEligibility.likely_eligible === false
                          ? t('agents.retrenchment-navigator.eis.unlikely')
                          : t('agents.retrenchment-navigator.eis.unknown')}
                    </p>
                    {eisEligibility.note && (
                      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">{eisEligibility.note}</p>
                    )}
                  </div>
                )}
                {noticePeriodStatus && noticePeriodStatus !== 'unknown' && (
                  <div className="bg-white border border-zinc-200 rounded-xl p-3.5 dark:bg-white/5 dark:border-white/10">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                      {t('agents.retrenchment-navigator.section.notice')}
                    </p>
                    <p
                      className={`text-sm font-medium mt-1 ${
                        noticePeriodStatus === 'sufficient'
                          ? 'text-green-700 dark:text-green-400'
                          : 'text-amber-700 dark:text-amber-400'
                      }`}
                    >
                      {noticePeriodStatus === 'sufficient'
                        ? t('agents.retrenchment-navigator.notice.sufficient')
                        : t('agents.retrenchment-navigator.notice.owed')}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Checklist — this is literally a to-do list of next steps, so
                it's styled as one (checkbox glyph) instead of a plain
                bulleted list indistinguishable from prose. */}
            {checklist.length > 0 && (
              <div className="bg-white border border-zinc-200 rounded-xl p-4 dark:bg-white/5 dark:border-white/10">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500 mb-2">
                  {t('agents.retrenchment-navigator.section.checklist')}
                </p>
                <ul className="flex flex-col gap-2">
                  {checklist.map((c) => (
                    <li key={c} className="flex items-start gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" className="w-4 h-4 mt-0.5 flex-shrink-0 text-teal-600 dark:text-teal-400" aria-hidden>
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
          </section>
        )}

        <ChatBubbles messages={messages} />
        {loading && <AgentLoadingSkeleton message={t('agents.retrenchment-navigator.thinking')} />}
        <div ref={bottomRef} />

        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-2 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          {nextPrompt && <p className="text-sm text-nk-official-dim dark:text-nk-official">{nextPrompt}</p>}
          <textarea
            className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-teal-500/50 focus:outline-none focus:ring-1 focus:ring-teal-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t('agents.retrenchment-navigator.placeholder')}
          />
          <button
            type="button"
            disabled={loading || !message.trim()}
            onClick={() => void send()}
            className="self-end px-4 py-2 bg-teal-600 hover:bg-teal-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-teal-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading
              ? t('agents.retrenchment-navigator.thinking')
              : sessionId
                ? t('agents.retrenchment-navigator.button.continue')
                : t('agents.retrenchment-navigator.button.start')}
          </button>
        </section>
      </motion.div>
    </>
  );
}

export default function RetrenchmentNavigatorPage() {
  return (
    <Suspense>
      <RetrenchmentNavigatorPageInner />
    </Suspense>
  );
}
