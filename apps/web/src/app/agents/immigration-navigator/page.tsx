'use client';

import { Suspense, useRef, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChatBubbles, QuickReplies, type ChatMessage } from '@/components/agents/ChatBubbles';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { useI18n } from '@/lib/i18n';

// This agent's `language` field is the target language for its guided
// intake — deriving it from the active UI locale instead of hardcoding
// 'bm' follows the same precedented pattern used by grant-draft-generator/
// sme-compliance-navigator's `queryLanguage`.
function localeToApiLanguage(locale: string): 'bm' | 'en' | 'zh' {
  if (locale === 'ms') return 'bm';
  if (locale === 'zh') return 'zh';
  return 'en';
}

// Deel-style binary/multi intent-select cards shown before any form field
// (Mobbin reference: Deel's Visa Eligibility Check flow) — replaces jumping
// straight into an open free-text box with an explicit "what are you trying
// to do" choice. Each card sends its message as the agent's first turn.
const INTENTS: { id: string; icon: string; titleKey: string; descKey: string; message: string }[] = [
  { id: 'work', icon: '💼', titleKey: 'agents.immigration-navigator.intent.work.title', descKey: 'agents.immigration-navigator.intent.work.desc', message: 'I want to work in Malaysia' },
  { id: 'study', icon: '🎓', titleKey: 'agents.immigration-navigator.intent.study.title', descKey: 'agents.immigration-navigator.intent.study.desc', message: 'Student visa for university' },
  { id: 'visit', icon: '✈️', titleKey: 'agents.immigration-navigator.intent.visit.title', descKey: 'agents.immigration-navigator.intent.visit.desc', message: 'Visit family for 3 months' },
  { id: 'business', icon: '🏢', titleKey: 'agents.immigration-navigator.intent.business.title', descKey: 'agents.immigration-navigator.intent.business.desc', message: 'Start a business in Kuala Lumpur' },
  { id: 'extend', icon: '🔄', titleKey: 'agents.immigration-navigator.intent.extend.title', descKey: 'agents.immigration-navigator.intent.extend.desc', message: 'Extend my current visa' },
  // These three route straight into the named e-service reference track
  // (service_router_node's keyword detection — "mdac"/"plks"/"pvip" — see
  // app/agents/immigration_navigator/nodes.py) rather than the general
  // visa-intake flow above, so their message text is chosen to match those
  // keywords exactly.
  { id: 'mdac', icon: '🛂', titleKey: 'agents.immigration-navigator.intent.mdac.title', descKey: 'agents.immigration-navigator.intent.mdac.desc', message: 'I need to submit my MDAC before arrival' },
  { id: 'eplks', icon: '🪪', titleKey: 'agents.immigration-navigator.intent.eplks.title', descKey: 'agents.immigration-navigator.intent.eplks.desc', message: 'I need to renew my PLKS' },
  { id: 'pvip', icon: '💎', titleKey: 'agents.immigration-navigator.intent.pvip.title', descKey: 'agents.immigration-navigator.intent.pvip.desc', message: "I'm interested in the PVIP" },
];

function ImmigrationNavigatorPageInner() {
  const { t, locale } = useI18n();
  const { start, continue: cont, get } = useAgentApi();
  const searchParams = useSearchParams();
  const [intentChosen, setIntentChosen] = useState(false);
  const [message, setMessage] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnsCount, setTurnsCount] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 'welcome', role: 'bot', content: t('agents.immigration-navigator.welcome') },
  ]);
  const [quickReplies, setQuickReplies] = useState<string[]>([]);
  const [checklist, setChecklist] = useState<string[]>([]);
  const [visaType, setVisaType] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [prefilledReference, setPrefilledReference] = useState<Array<{ field: string; value: string }>>([]);
  const [portalUrl, setPortalUrl] = useState<string | null>(null);
  const [portalNote, setPortalNote] = useState<string | null>(null);
  const [enquiryDraft, setEnquiryDraft] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const copyToClipboard = (text: string, key: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopiedField(key);
      setTimeout(() => setCopiedField((k) => (k === key ? null : k)), 1500);
    });
  };
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Resume from History's "?run=<agent_runs.id>" link. The chat transcript
  // itself isn't persisted server-side (only the latest structured output
  // is), so this can't replay every prior message — it restores the
  // structured state (visa_type/checklist/warnings/session_id so a
  // follow-up message continues the real LangGraph thread) and adds one
  // synthetic bot message summarizing where the conversation left off,
  // which is honest about what's actually being restored. Silent fallback
  // to a fresh intake on any failure (bad/expired link) rather than an
  // error.
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const run = await get(`/api/v1/agent-runs/${runId}`);
        const out = (run.output as Record<string, unknown>) ?? {};
        setSessionId(typeof run.session_id === 'string' ? run.session_id : null);
        setIntentChosen(true);
        setTurnsCount(typeof run.turns_count === 'number' ? run.turns_count : 0);
        if (out.visa_type) setVisaType(String(out.visa_type));
        if (Array.isArray(out.checklist)) setChecklist(out.checklist as string[]);
        if (Array.isArray(out.warnings)) setWarnings(out.warnings as string[]);
        if (Array.isArray(out.prefilled_reference)) setPrefilledReference(out.prefilled_reference as Array<{ field: string; value: string }>);
        if (typeof out.portal_url === 'string' && out.portal_url) setPortalUrl(out.portal_url);
        if (typeof out.portal_note === 'string') setPortalNote(out.portal_note);
        if (typeof out.enquiry_draft === 'string') setEnquiryDraft(out.enquiry_draft);
        const lastResponse = out.response ?? out.summary ?? out.output;
        if (lastResponse) {
          setMessages((prev) => [
            ...prev,
            { id: 'resumed', role: 'bot', content: String(lastResponse) },
          ]);
        }
      } catch {
        /* stale/invalid run id — stays on the fresh intake flow */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = async (text?: string) => {
    const msg = text ?? message;
    if (!msg.trim()) return;
    setIntentChosen(true);
    const userMsg: ChatMessage = { id: `u_${Date.now()}`, role: 'user', content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setMessage('');
    setQuickReplies([]);
    setLoading(true);

    try {
      const res = sessionId
        ? await cont('immigration-navigator', { session_id: sessionId, message: msg })
        : await start('immigration-navigator', { message: msg, language: localeToApiLanguage(locale) });

      if (!sessionId && res.session_id) setSessionId(String(res.session_id));
      setTurnsCount((n) => n + 1);

      const out = (res.output as Record<string, unknown>) ?? res;
      // This agent's state has no free-text "response"/"summary" field —
      // ever (confirmed in app/agents/immigration_navigator/nodes.py: intake
      // turns set next_prompt, the completion turn sets visa_type/checklist/
      // warnings only). The old response ?? summary ?? output ?? JSON.stringify
      // chain always fell through to JSON.stringify(out), dumping the raw
      // state object into the chat bubble as a bug report caught (a
      // {"session_id":...,"nationality":null,...} wall of text instead of a
      // sentence). next_prompt covers "needs more info" turns; the
      // completion turn's real content already renders in the visaType/
      // checklist/warnings panel above the chat, so the bubble just
      // acknowledges it — matching retrenchment-navigator's established
      // next_prompt-or-result_ready pattern for the same agent shape.
      const botText = String(
        (res.next_prompt as string) ?? (out.next_prompt as string) ?? t('agents.immigration-navigator.result_ready'),
      );
      const botMsg: ChatMessage = { id: `b_${Date.now()}`, role: 'bot', content: botText };
      setMessages((prev) => [...prev, botMsg]);

      // Extract structured data
      if (out.visa_type) setVisaType(String(out.visa_type));
      if (Array.isArray(out.checklist)) setChecklist(out.checklist as string[]);
      if (Array.isArray(out.warnings)) setWarnings(out.warnings as string[]);
      if (Array.isArray(out.prefilled_reference)) setPrefilledReference(out.prefilled_reference as Array<{ field: string; value: string }>);
      if (typeof out.portal_url === 'string' && out.portal_url) setPortalUrl(out.portal_url);
      if (typeof out.portal_note === 'string') setPortalNote(out.portal_note);
      if (typeof out.enquiry_draft === 'string') setEnquiryDraft(out.enquiry_draft);

      // Generate contextual quick replies. QuickReplies sends the label text
      // itself as the next message (see onSelect below) — these were
      // hardcoded English regardless of locale, so a bm/zh conversation
      // would suddenly get an English reply injected mid-thread. Localized;
      // this also makes the language tag fix above actually consistent end
      // to end, not just on the first turn.
      if (res.next_prompt || out.next_prompt) {
        setQuickReplies([
          t('agents.immigration-navigator.quick_reply.yes'),
          t('agents.immigration-navigator.quick_reply.no'),
          t('agents.immigration-navigator.quick_reply.more_details'),
          t('agents.immigration-navigator.quick_reply.documents'),
        ]);
      } else {
        setQuickReplies([]);
      }
    } catch {
      const errMsg: ChatMessage = { id: `e_${Date.now()}`, role: 'bot', content: t('agents.immigration-navigator.error') };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <AgentPageHeader title={t('agents.immigration-navigator.title')} />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        {!intentChosen && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
            <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              {t('agents.immigration-navigator.intent_step')}
            </p>
            <h2 className="font-semibold text-sm">{t('agents.immigration-navigator.intent_prompt')}</h2>
            <div className="grid gap-2 sm:grid-cols-2">
              {INTENTS.map((intent) => (
                <button
                  key={intent.id}
                  type="button"
                  onClick={() => void send(intent.message)}
                  className="flex flex-col items-start gap-1 rounded-xl border border-zinc-200 p-3 text-left transition-colors hover:border-teal-400 hover:bg-teal-50 dark:border-white/10 dark:hover:bg-teal-500/10"
                >
                  <span className="text-lg" aria-hidden>{intent.icon}</span>
                  <span className="text-sm font-semibold">{t(intent.titleKey)}</span>
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">{t(intent.descKey)}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setIntentChosen(true)}
              className="self-start text-xs text-zinc-500 hover:underline dark:text-zinc-400"
            >
              {t('agents.immigration-navigator.intent_skip')}
            </button>
          </section>
        )}

        {intentChosen && (
          <>
            {visaType != null && (
              <section className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
                <h2 className="font-semibold text-teal-800 dark:text-teal-300">{visaType}</h2>
                <ul className="mt-2 text-sm list-disc pl-5 space-y-1 text-zinc-700 dark:text-zinc-300">{checklist.map((c) => <li key={c}>{c}</li>)}</ul>
                {warnings.length > 0 && (
                  <div className="mt-3 text-xs text-amber-800 bg-amber-50 border border-amber-100 p-2 rounded-lg space-y-1 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
                    {warnings.map((w) => <p key={w}>{w}</p>)}
                  </div>
                )}
              </section>
            )}

            {/* Named-e-service track (MDAC/ePLKS/MM2H/foreign-worker/
                passport/PVIP): a copy-paste reference, never a submission —
                see immigration_navigator/nodes.py's module docstring for
                why. Each row has its own copy button since the whole point
                is pasting these one at a time into the real government
                form. */}
            {prefilledReference.length > 0 && (
              <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="font-semibold text-teal-800 dark:text-teal-300">{portalNote ?? t('agents.immigration-navigator.reference_title')}</h2>
                  {portalUrl && (
                    <a
                      href={portalUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-shrink-0 px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-xs font-semibold transition-colors"
                    >
                      {t('agents.immigration-navigator.open_portal')}
                    </a>
                  )}
                </div>
                <div className="flex flex-col divide-y divide-zinc-100 dark:divide-white/10">
                  {prefilledReference.map((row) => (
                    <div key={row.field} className="flex items-center justify-between gap-3 py-2">
                      <div className="min-w-0">
                        <p className="text-[11px] text-zinc-400 dark:text-zinc-500">{row.field}</p>
                        <p className="text-sm font-medium truncate">{row.value || '—'}</p>
                      </div>
                      {row.value && (
                        <button
                          type="button"
                          onClick={() => copyToClipboard(row.value, row.field)}
                          className="flex-shrink-0 text-xs font-medium text-nk-official-dim hover:text-nk-official transition-colors"
                        >
                          {copiedField === row.field ? t('agents.immigration-navigator.copied') : t('agents.immigration-navigator.copy')}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                {warnings.length > 0 && (
                  <div className="text-xs text-amber-800 bg-amber-50 border border-amber-100 p-2 rounded-lg space-y-1 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
                    {warnings.map((w) => <p key={w}>{w}</p>)}
                  </div>
                )}
              </section>
            )}

            {/* SPO enquiry-drafting track: draft text + the copy button —
                same "user submits it themselves" pattern. */}
            {enquiryDraft != null && (
              <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="font-semibold text-teal-800 dark:text-teal-300">{t('agents.immigration-navigator.spo_draft_title')}</h2>
                  <a
                    href="https://eapp.imi.gov.my/spo"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-shrink-0 px-3 py-1.5 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-xs font-semibold transition-colors"
                  >
                    {t('agents.immigration-navigator.open_portal')}
                  </a>
                </div>
                <p className="text-sm whitespace-pre-wrap text-zinc-700 dark:text-zinc-300 bg-zinc-50 dark:bg-white/5 rounded-lg p-3">{enquiryDraft}</p>
                <button
                  type="button"
                  onClick={() => copyToClipboard(enquiryDraft, 'spo_draft')}
                  className="self-start text-xs font-medium text-nk-official-dim hover:text-nk-official transition-colors"
                >
                  {copiedField === 'spo_draft' ? t('agents.immigration-navigator.copied') : t('agents.immigration-navigator.copy')}
                </button>
                {warnings.length > 0 && (
                  <div className="text-xs text-amber-800 bg-amber-50 border border-amber-100 p-2 rounded-lg space-y-1 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
                    {warnings.map((w) => <p key={w}>{w}</p>)}
                  </div>
                )}
              </section>
            )}

            <ChatBubbles messages={messages} />
            {loading && <AgentLoadingSkeleton message={t('agents.immigration-navigator.thinking')} />}
            <div ref={bottomRef} />

            <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-2 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
              {/* Step-labeled turn indicator (Mobbin reference: Deel's
                  "Step 1: Pre-hire assessment") — the underlying flow is
                  still a conversational multi-turn intake, not separately
                  named form fields, but labeling each turn as a step gives
                  the same sense of structured progress. */}
              {/* The agent's next-prompt text itself is NOT repeated here —
                  it already renders as the latest bot bubble in
                  ChatBubbles right above this card, so showing it a
                  second time read as a duplicated message rather than a
                  "next step" cue. */}
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                {t('agents.immigration-navigator.turn_step').replace('{n}', String(turnsCount + 1))}
              </p>
              <QuickReplies options={quickReplies} onSelect={(opt) => void send(opt)} />
              <textarea
                className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-teal-500/50 focus:outline-none focus:ring-1 focus:ring-teal-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
                rows={3}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder={t('agents.immigration-navigator.placeholder')}
              />
              <button
                type="button"
                disabled={loading || !message.trim()}
                onClick={() => void send()}
                className="self-end px-4 py-2 bg-teal-600 hover:bg-teal-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-teal-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
              >
                {loading
                  ? t('agents.immigration-navigator.thinking')
                  : sessionId
                    ? t('agents.immigration-navigator.button.continue')
                    : t('agents.immigration-navigator.button.start')}
              </button>
            </section>
          </>
        )}
      </motion.div>
    </>
  );
}

export default function ImmigrationNavigatorPage() {
  return (
    <Suspense>
      <ImmigrationNavigatorPageInner />
    </Suspense>
  );
}
