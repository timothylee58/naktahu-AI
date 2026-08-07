'use client';

import { useRef, useState, useEffect } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';

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

function formatAmount(g: Grant): string {
  if (g.amount_min_myr == null && g.amount_max_myr == null) return '';
  if (g.amount_min_myr != null && g.amount_max_myr != null) {
    return `RM ${g.amount_min_myr.toLocaleString()} – RM ${g.amount_max_myr.toLocaleString()}`;
  }
  const amt = g.amount_max_myr ?? g.amount_min_myr;
  return amt != null ? `Up to RM ${amt.toLocaleString()}` : '';
}

function formatDeadline(g: Grant): string {
  if (g.deadline_is_rolling) return 'Rolling applications';
  if (!g.application_deadline) return '';
  return `Closes ${g.application_deadline}`;
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
        <span className="flex-shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300">
          {Math.round(grant.eligibility_score * 100)}% match
        </span>
      </div>
      {grant.agency && <p className="text-zinc-500 text-xs mt-0.5 dark:text-zinc-500">{grant.agency}</p>}
      <p className="text-xs text-zinc-500 mt-1 dark:text-zinc-500">
        {formatAmount(grant)}
        {formatAmount(grant) && formatDeadline(grant) ? ' · ' : ''}
        {formatDeadline(grant)}
      </p>
      {dimmed && grant.ineligibility_reasons.length > 0 && (
        <p className="text-xs text-amber-700 mt-2 dark:text-amber-400">{grant.ineligibility_reasons[0]}</p>
      )}
      <div className="flex items-center gap-3 mt-2">
        {grant.application_url && (
          <a
            href={grant.application_url}
            className="text-blue-600 text-xs dark:text-blue-400"
            target="_blank"
            rel="noreferrer"
          >
            Apply now →
          </a>
        )}
        {!dimmed && (
          <Link
            href={draftLinkHref(grant.programme_name, profile)}
            className="text-emerald-600 text-xs font-medium dark:text-emerald-400"
          >
            Draft application →
          </Link>
        )}
      </div>
    </motion.li>
  );
}

export default function GrantFinderPage() {
  const { start, continue: cont } = useAgentApi();
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
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [phase, nextQuestion]);

  const canStart = sector.length > 0 && businessType.length > 0 && registeredMonths.trim() !== '' && isBumiputera !== null;

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

  const submitIntake = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await start('eligibility-agent', {
        sector: sector[0],
        business_type: businessType[0],
        registered_months: Number(registeredMonths) || 0,
        annual_revenue_myr: Number(annualRevenue) || 0,
        is_bumiputera: isBumiputera,
        language: 'bm',
      });
      applyResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.');
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
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="flex items-center gap-2 px-4 pt-4 sm:px-6">
        <h1 className="text-lg font-bold tracking-tight">Grant Finder</h1>
        <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-semibold dark:bg-blue-500/15 dark:text-blue-300">Recommended</span>
      </div>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Match your business profile to Malaysian government grants — Cradle, MDEC, SME Corp, MTDC, and more — with scoring, near-miss detection, and a recommended application sequence.
        </p>

        {phase === 'intake' && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-2 dark:text-zinc-400">Sector</p>
              <ChipSelector options={SECTOR_OPTIONS} selected={sector} onToggle={(id) => setSector([id])} multiple={false} size="sm" />
            </div>
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-2 dark:text-zinc-400">Business type</p>
              <ChipSelector options={BUSINESS_TYPE_OPTIONS} selected={businessType} onToggle={(id) => setBusinessType([id])} multiple={false} size="sm" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">Months registered</span>
                <input
                  type="number"
                  min={0}
                  value={registeredMonths}
                  onChange={(e) => setRegisteredMonths(e.target.value)}
                  placeholder="e.g. 18"
                  className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-transparent focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">Annual revenue (RM)</span>
                <input
                  type="number"
                  min={0}
                  value={annualRevenue}
                  onChange={(e) => setAnnualRevenue(e.target.value)}
                  placeholder="e.g. 250000"
                  className="border border-zinc-200 rounded-xl px-3 py-2 text-sm bg-transparent focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
                />
              </label>
            </div>
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-2 dark:text-zinc-400">Bumiputera-owned?</p>
              <div className="flex gap-2">
                {[{ id: true, label: 'Yes' }, { id: false, label: 'No' }].map((opt) => (
                  <button
                    key={String(opt.id)}
                    type="button"
                    onClick={() => setIsBumiputera(opt.id)}
                    className={`px-4 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      isBumiputera === opt.id
                        ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-500/15 dark:text-blue-300'
                        : 'border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
            <button
              type="button"
              disabled={loading || !canStart}
              onClick={() => void submitIntake()}
              className="self-end px-4 py-2 bg-blue-600 hover:bg-blue-500 transition-colors text-white rounded-xl text-sm font-semibold disabled:opacity-50"
            >
              {loading ? 'Matching…' : 'Find grants'}
            </button>
            {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
          </section>
        )}

        {phase === 'chat' && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
            {nextQuestion && <p className="text-sm text-blue-700 dark:text-blue-400">{nextQuestion}</p>}
            <textarea
              className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
              rows={2}
              value={chatReply}
              onChange={(e) => setChatReply(e.target.value)}
              placeholder="Type your answer…"
            />
            <button
              type="button"
              disabled={loading || !chatReply.trim()}
              onClick={() => void sendChatReply()}
              className="self-end px-4 py-2 bg-blue-600 hover:bg-blue-500 transition-colors text-white rounded-xl text-sm font-semibold disabled:opacity-50"
            >
              {loading ? '…' : 'Continue'}
            </button>
            {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
            <div ref={bottomRef} />
          </section>
        )}

        {loading && phase !== 'results' && <AgentLoadingSkeleton />}

        {phase === 'results' && (
          <>
            {matchedGrants.length > 0 ? (
              <div>
                <p className="text-xs font-semibold text-zinc-500 mb-2 dark:text-zinc-400">
                  {matchedGrants.length} matching grant{matchedGrants.length === 1 ? '' : 's'}
                </p>
                <ul className="flex flex-col gap-3">
                  {matchedGrants.map((g) => (
                    <GrantCard key={g.programme_name} grant={g} profile={profileForDraft} />
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">No fully-matching grants found for this profile.</p>
            )}
            {nearMissGrants.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-zinc-500 mb-2 mt-2 dark:text-zinc-400">
                  Near-miss — close, but doesn&apos;t fully qualify yet
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
              className="self-start text-xs font-semibold text-blue-600 hover:text-blue-500 dark:text-blue-400"
            >
              Start a new search
            </button>
          </>
        )}
      </motion.div>
    </>
  );
}
