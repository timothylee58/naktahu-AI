'use client';

import { Suspense, useRef, useState, useEffect } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { useI18n } from '@/lib/i18n';

// This agent's `language` field is the target language for grant matching —
// deriving it from the active UI locale instead of hardcoding 'bm' follows
// the same precedented pattern used by grant-draft-generator/
// sme-compliance-navigator's `queryLanguage`.
function localeToApiLanguage(locale: string): 'bm' | 'en' | 'zh' {
  if (locale === 'ms') return 'bm';
  if (locale === 'zh') return 'zh';
  return 'en';
}

function fmt(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), template);
}

// Sectors matching grant_database.eligible_sectors seed values (migration
// 020) — NOT arbitrary labels. A mismatch here silently zeroes out every
// grant match, since eligibility_agent/analyst_node.py does an exact string
// membership check against each grant's eligible_sectors array.
const SECTOR_OPTIONS: ChipOption[] = [
  { id: 'technology', label: 'Technology', icon: '🖥' },
  { id: 'ai', label: 'AI', icon: '🤖' },
  { id: 'fintech', label: 'Fintech', icon: '💳' },
  { id: 'edtech', label: 'EdTech', icon: '📚' },
  { id: 'healthtech', label: 'HealthTech', icon: '⚕️' },
  { id: 'digital', label: 'Digital', icon: '📱' },
  { id: 'deeptech', label: 'DeepTech', icon: '🔬' },
  { id: 'biotech', label: 'BioTech', icon: '🧬' },
  { id: 'manufacturing', label: 'Manufacturing', icon: '🏭' },
  { id: 'agriculture', label: 'Agriculture', icon: '🌾' },
  { id: 'services', label: 'Services', icon: '🛎' },
];

// eligibility_agent/state.py: business_type: sole_prop|sdn_bhd|startup|llp|cooperative
const BUSINESS_TYPE_OPTIONS: ChipOption[] = [
  { id: 'sole_prop', label: 'Sole Proprietor', icon: '🏪' },
  { id: 'sdn_bhd', label: 'Sdn Bhd', icon: '🏢' },
  { id: 'startup', label: 'Startup', icon: '🚀' },
  { id: 'llp', label: 'LLP', icon: '🤝' },
  { id: 'cooperative', label: 'Cooperative', icon: '👥' },
];

interface Grant {
  programme_name: string;
  agency: string | null;
  grant_type: string | null;
  amount_min_myr: number | null;
  amount_max_myr: number | null;
  application_deadline: string | null;
  deadline_is_rolling: boolean;
  application_url: string | null;
  eligibility_score: number;
  eligibility_reasons: string[];
  ineligibility_reasons: string[];
}

function parseGrant(raw: unknown): Grant | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const programme_name = typeof r.programme_name === 'string' ? r.programme_name : '';
  if (!programme_name) return null;
  return {
    programme_name,
    agency: typeof r.agency === 'string' ? r.agency : null,
    grant_type: typeof r.grant_type === 'string' ? r.grant_type : null,
    amount_min_myr: typeof r.amount_min_myr === 'number' ? r.amount_min_myr : null,
    amount_max_myr: typeof r.amount_max_myr === 'number' ? r.amount_max_myr : null,
    application_deadline: typeof r.application_deadline === 'string' ? r.application_deadline : null,
    deadline_is_rolling: Boolean(r.deadline_is_rolling),
    application_url: typeof r.application_url === 'string' && r.application_url ? r.application_url : null,
    eligibility_score: typeof r.eligibility_score === 'number' ? r.eligibility_score : 0,
    eligibility_reasons: Array.isArray(r.eligibility_reasons) ? (r.eligibility_reasons as string[]) : [],
    ineligibility_reasons: Array.isArray(r.ineligibility_reasons) ? (r.ineligibility_reasons as string[]) : [],
  };
}

function parseGrants(raw: unknown): Grant[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(parseGrant).filter((g): g is Grant => g !== null);
}

function formatAmount(g: Grant, t: (key: string) => string): string {
  if (g.amount_min_myr == null && g.amount_max_myr == null) return '';
  if (g.amount_min_myr != null && g.amount_max_myr != null) {
    return fmt(t('agents.grant-finder.amount.range'), {
      min: g.amount_min_myr.toLocaleString(),
      max: g.amount_max_myr.toLocaleString(),
    });
  }
  const amt = g.amount_max_myr ?? g.amount_min_myr;
  return amt != null ? fmt(t('agents.grant-finder.amount.up_to'), { amt: amt.toLocaleString() }) : '';
}

function formatDeadline(g: Grant, t: (key: string) => string): string {
  if (g.deadline_is_rolling) return t('agents.grant-finder.deadline.rolling');
  if (!g.application_deadline) return '';
  return fmt(t('agents.grant-finder.deadline.closes'), { date: g.application_deadline });
}

interface ProfileForDraftLink {
  businessType: string;
  sector: string;
  registeredMonths: string;
  annualRevenue: string;
  isBumiputera: boolean | null;
}

function draftLinkHref(programmeName: string, profile: ProfileForDraftLink): string {
  const params = new URLSearchParams({ programme: programmeName });
  if (profile.businessType) params.set('business_type', profile.businessType);
  if (profile.sector) params.set('sector', profile.sector);
  if (profile.registeredMonths) params.set('registered_months', profile.registeredMonths);
  if (profile.annualRevenue) params.set('annual_revenue_myr', profile.annualRevenue);
  if (profile.isBumiputera !== null) params.set('is_bumiputera', String(profile.isBumiputera));
  return `/agents/grant-draft-generator?${params.toString()}`;
}

function GrantCard({ grant, dimmed, profile }: { grant: Grant; dimmed?: boolean; profile: ProfileForDraftLink }) {
  const { t } = useI18n();
  const amount = formatAmount(grant, t);
  const deadline = formatDeadline(grant, t);
  return (
    <motion.li
      whileHover={{ y: -2 }}
      className={`rounded-2xl p-4 text-sm shadow-sm transition-shadow hover:shadow-md border ${
        dimmed
          ? 'bg-zinc-50 border-zinc-200 dark:bg-white/[0.02] dark:border-white/5'
          : 'bg-white border-zinc-200 dark:bg-white/5 dark:border-white/10'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold text-zinc-900 dark:text-white">{grant.programme_name}</p>
        <span className="flex-shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full bg-nk-official/10 text-nk-official-dim dark:bg-nk-official/15 dark:text-nk-official">
          {fmt(t('agents.grant-finder.card.match'), { n: Math.round(grant.eligibility_score * 100) })}
        </span>
      </div>
      {grant.agency && <p className="text-zinc-500 text-xs mt-0.5 dark:text-zinc-500">{grant.agency}</p>}
      <p className="text-xs text-zinc-500 mt-1 dark:text-zinc-500">
        {amount}
        {amount && deadline ? ' · ' : ''}
        {deadline}
      </p>
      {dimmed && grant.ineligibility_reasons.length > 0 && (
        <p className="text-xs text-amber-700 mt-2 dark:text-amber-400">{grant.ineligibility_reasons[0]}</p>
      )}
      <div className="flex items-center gap-3 mt-2">
        {grant.application_url && (
          <a
            href={grant.application_url}
            className="text-nk-official-dim text-xs dark:text-nk-official"
            target="_blank"
            rel="noreferrer"
          >
            {t('agents.grant-finder.card.apply')}
          </a>
        )}
        {!dimmed && (
          <Link
            href={draftLinkHref(grant.programme_name, profile)}
            className="text-emerald-600 text-xs font-medium dark:text-emerald-400"
          >
            {t('agents.grant-finder.card.draft')}
          </Link>
        )}
      </div>
    </motion.li>
  );
}

function GrantFinderPageInner() {
  const { t, locale } = useI18n();
  const { start, continue: cont, get } = useAgentApi();
  const searchParams = useSearchParams();
  const [sector, setSector] = useState<string[]>([]);
  const [businessType, setBusinessType] = useState<string[]>([]);
  const [registeredMonths, setRegisteredMonths] = useState('');
  const [annualRevenue, setAnnualRevenue] = useState('');
  const [isBumiputera, setIsBumiputera] = useState<boolean | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [phase, setPhase] = useState<'intake' | 'chat' | 'results'>('intake');
  const [nextQuestion, setNextQuestion] = useState<string | null>(null);
  const [chatReply, setChatReply] = useState('');
  const [matchedGrants, setMatchedGrants] = useState<Grant[]>([]);
  const [nearMissGrants, setNearMissGrants] = useState<Grant[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Set only once the user actually tries to submit with missing/invalid
  // fields — inline errors shouldn't appear before someone's had a chance
  // to fill the form in. Replaces the old silently-disabled submit button
  // (a real UX complaint: nothing told the user *why* the button wouldn't
  // respond) with a button that's always clickable and explains itself.
  const [attemptedSubmit, setAttemptedSubmit] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [phase, nextQuestion]);

  const revenueValue = annualRevenue.trim() === '' ? null : Number(annualRevenue);
  const revenueInvalid = revenueValue !== null && (Number.isNaN(revenueValue) || revenueValue < 0);
  const canStart =
    sector.length > 0 && businessType.length > 0 && registeredMonths.trim() !== '' && isBumiputera !== null && !revenueInvalid;

  // Threaded onto each GrantCard's "Draft application" link so Grant Draft
  // Generator opens pre-filled instead of the user re-typing everything —
  // this is the same profile that just found these grants.
  const profileForDraft: ProfileForDraftLink = {
    businessType: businessType[0] ?? '',
    sector: sector[0] ?? '',
    registeredMonths,
    annualRevenue,
    isBumiputera,
  };

  const applyResult = (res: Record<string, unknown>) => {
    if (!sessionId && res.session_id) setSessionId(String(res.session_id));
    const out = (res.output as Record<string, unknown>) ?? {};
    const completed = res.status === 'completed' && !res.awaiting_hitl;
    if (completed) {
      setMatchedGrants(parseGrants(out.matched_grants));
      setNearMissGrants(parseGrants(out.near_miss_grants));
      setPhase('results');
      setNextQuestion(null);
    } else {
      setNextQuestion((out.next_question as string) ?? 'Could you tell me a bit more about your business?');
      setPhase('chat');
    }
  };

  // Resume from History's "?run=<agent_runs.id>" link. Note: this page's
  // backend agent name is 'eligibility-agent' (grant-finder is the
  // frontend-only slug — see agents.ts's backendName override), but the
  // agent_runs row is already keyed by 'eligibility-agent' too (that's
  // what _log_run was called with), so no extra name mapping is needed
  // here. Reuses applyResult() so resumed sessions go through the exact
  // same completed-vs-mid-intake branching a live response would. Silent
  // fallback to a fresh intake on any failure (bad/expired link) rather
  // than an error.
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const run = await get(`/api/v1/agent-runs/${runId}`);
        applyResult({
          session_id: run.session_id,
          status: run.completion_status,
          awaiting_hitl: run.completion_status !== 'completed',
          output: run.output,
        });
      } catch {
        /* stale/invalid run id — stays on the fresh intake flow */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitIntake = async () => {
    if (!canStart) {
      setAttemptedSubmit(true);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await start('eligibility-agent', {
        sector: sector[0],
        business_type: businessType[0],
        registered_months: Number(registeredMonths) || 0,
        annual_revenue_myr: Number(annualRevenue) || 0,
        is_bumiputera: isBumiputera,
        language: localeToApiLanguage(locale),
      });
      applyResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('agents.error.generic'));
    } finally {
      setLoading(false);
    }
  };

  const sendChatReply = async () => {
    const msg = chatReply.trim();
    if (!msg || !sessionId) return;
    setChatReply('');
    setLoading(true);
    setError(null);
    try {
      const res = await cont('eligibility-agent', { session_id: sessionId, message: msg });
      applyResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('agents.error.generic'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <AgentPageHeader title={t('agents.grant-finder.title')} badge={t('agents.grant-finder.badge')} />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        <p className="text-sm text-zinc-600 dark:text-zinc-400">{t('agents.grant-finder.intro')}</p>

        {phase === 'intake' && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-1 dark:text-zinc-400">
                {t('agents.grant-finder.sector.label')} <span className="text-red-500">*</span>
                <span className="ml-1 font-normal normal-case text-zinc-400 dark:text-zinc-500">{t('agents.grant-finder.choose_one')}</span>
              </p>
              <ChipSelector options={SECTOR_OPTIONS} selected={sector} onToggle={(id) => setSector([id])} multiple={false} size="sm" />
              {attemptedSubmit && sector.length === 0 && (
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">{t('agents.grant-finder.sector.required')}</p>
              )}
            </div>
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-1 dark:text-zinc-400">
                {t('agents.grant-finder.business_type.label')} <span className="text-red-500">*</span>
                <span className="ml-1 font-normal normal-case text-zinc-400 dark:text-zinc-500">{t('agents.grant-finder.choose_one')}</span>
              </p>
              <ChipSelector options={BUSINESS_TYPE_OPTIONS} selected={businessType} onToggle={(id) => setBusinessType([id])} multiple={false} size="sm" />
              <p className="text-xs text-zinc-400 mt-1 dark:text-zinc-500">{t('agents.grant-finder.business_type.note')}</p>
              {attemptedSubmit && businessType.length === 0 && (
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">{t('agents.grant-finder.business_type.required')}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                  {t('agents.grant-finder.months.label')} <span className="text-red-500">*</span>
                </span>
                <input
                  type="number"
                  min={0}
                  value={registeredMonths}
                  onChange={(e) => setRegisteredMonths(e.target.value)}
                  placeholder={t('agents.grant-finder.months.placeholder')}
                  className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-transparent focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10 dark:placeholder:text-zinc-500"
                />
                {attemptedSubmit && registeredMonths.trim() === '' && (
                  <span className="text-xs text-red-600 dark:text-red-400">{t('agents.grant-finder.months.required')}</span>
                )}
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">{t('agents.grant-finder.revenue.label')}</span>
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-zinc-400 dark:text-zinc-500">
                    RM
                  </span>
                  <input
                    type="number"
                    min={0}
                    value={annualRevenue}
                    onChange={(e) => setAnnualRevenue(e.target.value)}
                    placeholder={t('agents.grant-finder.revenue.placeholder')}
                    className="w-full border border-zinc-200 rounded-xl pl-9 pr-3 py-2 text-sm bg-transparent focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10 dark:placeholder:text-zinc-500"
                  />
                </div>
                {revenueInvalid && (
                  <span className="text-xs text-red-600 dark:text-red-400">{t('agents.grant-finder.revenue.invalid')}</span>
                )}
              </label>
            </div>
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-1 dark:text-zinc-400">
                {t('agents.grant-finder.bumiputera.label')} <span className="text-red-500">*</span>
              </p>
              <p className="text-xs text-zinc-400 mb-2 dark:text-zinc-500">{t('agents.grant-finder.bumiputera.note')}</p>
              <div className="flex gap-2">
                {[
                  { id: true, label: t('agents.grant-finder.bumiputera.yes') },
                  { id: false, label: t('agents.grant-finder.bumiputera.no') },
                ].map((opt) => (
                  <button
                    key={String(opt.id)}
                    type="button"
                    onClick={() => setIsBumiputera(opt.id)}
                    className={`px-4 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      isBumiputera === opt.id
                        ? 'border-nk-official/40 bg-nk-official/10 text-nk-official-dim dark:border-nk-official/40 dark:bg-nk-official/15 dark:text-nk-official'
                        : 'border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              {attemptedSubmit && isBumiputera === null && (
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">{t('agents.grant-finder.bumiputera.required')}</p>
              )}
            </div>
            <button
              type="button"
              disabled={loading}
              onClick={() => void submitIntake()}
              className="self-end px-4 py-2 bg-nk-official hover:bg-nk-official-dim transition-colors text-white rounded-xl text-sm font-semibold disabled:opacity-50"
            >
              {loading ? t('agents.grant-finder.matching') : t('agents.grant-finder.submit')}
            </button>
            {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
          </section>
        )}

        {phase === 'chat' && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
            {nextQuestion && <p className="text-sm text-nk-official-dim dark:text-nk-official">{nextQuestion}</p>}
            <textarea
              className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10 dark:placeholder:text-zinc-500"
              rows={2}
              value={chatReply}
              onChange={(e) => setChatReply(e.target.value)}
              placeholder={t('agents.grant-finder.chat_placeholder')}
            />
            <button
              type="button"
              disabled={loading || !chatReply.trim()}
              onClick={() => void sendChatReply()}
              className="self-end px-4 py-2 bg-nk-official hover:bg-nk-official-dim transition-colors text-white rounded-xl text-sm font-semibold disabled:opacity-50"
            >
              {loading ? t('agents.processing') : t('agents.grant-finder.continue')}
            </button>
            {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
            <div ref={bottomRef} />
          </section>
        )}

        {loading && phase !== 'results' && <AgentLoadingSkeleton message={t('agents.grant-finder.matching')} />}

        {phase === 'results' && (
          <>
            {matchedGrants.length > 0 ? (
              <div>
                <p className="text-xs font-semibold text-zinc-500 mb-2 dark:text-zinc-400">
                  {fmt(t('agents.grant-finder.results_count'), {
                    n: matchedGrants.length,
                    s: matchedGrants.length === 1 ? '' : 's',
                  })}
                </p>
                <ul className="flex flex-col gap-3">
                  {matchedGrants.map((g) => (
                    <GrantCard key={g.programme_name} grant={g} profile={profileForDraft} />
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('agents.grant-finder.no_matches')}</p>
            )}
            {nearMissGrants.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-zinc-500 mb-2 mt-2 dark:text-zinc-400">
                  {t('agents.grant-finder.near_miss_title')}
                </p>
                <ul className="flex flex-col gap-3">
                  {nearMissGrants.map((g) => (
                    <GrantCard key={g.programme_name} grant={g} dimmed profile={profileForDraft} />
                  ))}
                </ul>
              </div>
            )}
            <button
              type="button"
              onClick={() => {
                setPhase('intake');
                setSessionId(null);
                setMatchedGrants([]);
                setNearMissGrants([]);
              }}
              className="self-start text-xs font-semibold text-nk-official-dim hover:text-nk-official dark:text-nk-official"
            >
              {t('agents.grant-finder.new_search')}
            </button>
          </>
        )}
      </motion.div>
    </>
  );
}

export default function GrantFinderPage() {
  return (
    <Suspense>
      <GrantFinderPageInner />
    </Suspense>
  );
}
