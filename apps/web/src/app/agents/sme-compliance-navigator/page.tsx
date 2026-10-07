'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { mapApiErrorDetail } from '@/lib/auth-headers';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { useI18n } from '@/lib/i18n';

interface ChecklistItem {
  domain: string;
  label: string;
  item: string;
}

const DOMAIN_COLORS: Record<string, string> = {
  tax: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  payroll: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  corporate: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
};

type Mode = 'guided' | 'freetext';
type FormStep = 'form' | 'review';

// Both catalogs were hardcoded English-only labels — every chip showed
// English text regardless of UI locale, unlike EVENT_OPTIONS right below
// them, which already correctly used labelKey + t(). Converted to
// functions of `t` for the same reason health-triage's option catalogs
// were: called from inside the component where locale context exists,
// option ids (used in composedProfile and the backend payload) unchanged.
function businessTypeOptions(t: (key: string) => string): ChipOption[] {
  return [
    { id: 'sole_prop', label: t('agents.sme-compliance-navigator.businesstype.sole_prop'), icon: '🏪' },
    { id: 'sdn_bhd', label: t('agents.sme-compliance-navigator.businesstype.sdn_bhd'), icon: '🏢' },
    { id: 'partnership', label: t('agents.sme-compliance-navigator.businesstype.partnership'), icon: '🤝' },
    { id: 'llp', label: t('agents.sme-compliance-navigator.businesstype.llp'), icon: '📋' },
  ];
}

function sectorOptions(t: (key: string) => string): ChipOption[] {
  return [
    { id: 'technology', label: t('agents.sme-compliance-navigator.sector.technology'), icon: '🖥' },
    { id: 'retail', label: t('agents.sme-compliance-navigator.sector.retail'), icon: '🛍' },
    { id: 'manufacturing', label: t('agents.sme-compliance-navigator.sector.manufacturing'), icon: '🏭' },
    { id: 'services', label: t('agents.sme-compliance-navigator.sector.services'), icon: '🛎' },
    { id: 'fnb', label: t('agents.sme-compliance-navigator.sector.fnb'), icon: '🍽' },
    { id: 'construction', label: t('agents.sme-compliance-navigator.sector.construction'), icon: '🏗' },
  ];
}

const EVENT_OPTIONS: { id: string; labelKey: string }[] = [
  { id: 'hiring_foreign_workers', labelKey: 'agents.sme-compliance-navigator.event.hiring_foreign_workers' },
  { id: 'new_registration', labelKey: 'agents.sme-compliance-navigator.event.new_registration' },
  { id: 'missed_filing', labelKey: 'agents.sme-compliance-navigator.event.missed_filing' },
  { id: 'crossed_sst_threshold', labelKey: 'agents.sme-compliance-navigator.event.crossed_sst_threshold' },
  { id: 'first_time_hiring', labelKey: 'agents.sme-compliance-navigator.event.first_time_hiring' },
];

function SmeComplianceNavigatorPageInner() {
  const { t, locale } = useI18n();
  const { start, get } = useAgentApi();
  const searchParams = useSearchParams();
  const [formStep, setFormStep] = useState<FormStep>('form');
  const [mode, setMode] = useState<Mode>('guided');
  const [businessProfile, setBusinessProfile] = useState('');
  const [businessType, setBusinessType] = useState<string[]>([]);
  const [sector, setSector] = useState<string[]>([]);
  const [headcount, setHeadcount] = useState('');
  const [annualRevenue, setAnnualRevenue] = useState('');
  const [events, setEvents] = useState<string[]>([]);
  const [checklist, setChecklist] = useState<ChecklistItem[] | null>(null);
  // Client-side completion state per checklist item (Vanta-style checkable
  // tasks, Mobbin reference) — keyed by index within the current checklist.
  // Resets on every new run since the backend doesn't persist checklist
  // state across sessions (no such table exists); scoped honestly as a
  // per-session tracker, not cross-visit history.
  const [doneItems, setDoneItems] = useState<Record<number, boolean>>({});
  const [staleWarnings, setStaleWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Was missing the zh case entirely (fell through to 'en'), same bug
  // class already fixed on research-synthesiser/retrenchment-navigator.
  const queryLanguage = locale === 'ms' ? 'bm' : locale === 'zh' ? 'zh' : 'en';

  const businessTypes = useMemo(() => businessTypeOptions(t), [t]);
  const sectors = useMemo(() => sectorOptions(t), [t]);

  // The backend agent still takes a single free-text business_profile string
  // (no structured fields in the API) — the guided form composes into that
  // same string instead of requiring a backend/schema change. Full OCR for
  // uploaded PDF/DOCX would need new backend document-parsing infrastructure,
  // which is out of scope here; this form is the no-backend-change middle
  // ground between "one text box" and "upload a document."
  //
  // The "N employees" / "annual revenue RM..." fragments were raw hardcoded
  // English regardless of locale — this composed string is both the actual
  // backend payload AND what's shown back to the user in the Review step,
  // so it needs the same localization as everything else on the page.
  const composedProfile = useMemo(() => {
    if (mode === 'freetext') return businessProfile;
    const parts: string[] = [];
    const btLabel = businessTypes.find((o) => o.id === businessType[0])?.label;
    const secLabel = sectors.find((o) => o.id === sector[0])?.label;
    if (btLabel && secLabel) parts.push(`${secLabel} ${btLabel}`);
    else if (btLabel) parts.push(btLabel);
    else if (secLabel) parts.push(secLabel);
    if (headcount) parts.push(`${headcount} ${t('agents.sme-compliance-navigator.employees_suffix')}`);
    if (annualRevenue) parts.push(`${t('agents.sme-compliance-navigator.revenue_prefix')}${annualRevenue}`);
    const eventLabels = events
      .map((id) => EVENT_OPTIONS.find((e) => e.id === id))
      .filter((e): e is { id: string; labelKey: string } => Boolean(e))
      .map((e) => t(e.labelKey));
    if (eventLabels.length > 0) parts.push(eventLabels.join(', '));
    return parts.join(', ');
  }, [mode, businessProfile, businessTypes, businessType, sectors, sector, headcount, annualRevenue, events, t]);

  const canRun = mode === 'freetext' ? businessProfile.trim().length > 0 : composedProfile.trim().length > 0;

  // Resume from History's "?run=<agent_runs.id>" link. This agent compiles
  // its LangGraph with no checkpointer at all (single-shot) — no
  // session_id/continue concept, just the stored checklist/warnings.
  // Silent fallback to the fresh form on any failure (bad/expired link).
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const run = await get(`/api/v1/agent-runs/${runId}`);
        const out = (run.output as Record<string, unknown>) ?? {};
        setChecklist((out.checklist as ChecklistItem[]) ?? []);
        setDoneItems({});
        setStaleWarnings((out.stale_warnings as string[]) ?? []);
      } catch {
        /* stale/invalid run id — stays on the fresh form */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    try {
      const data = await start('sme-compliance-navigator', {
        business_profile: composedProfile,
        language: queryLanguage,
      });
      setChecklist((data.checklist as ChecklistItem[]) ?? []);
      setDoneItems({});
      setStaleWarnings((data.stale_warnings as string[]) ?? []);
      setFormStep('form');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'start-failed';
      setError(message === 'sign-in-required' ? t('agents.error.sign_in') : mapApiErrorDetail(message, t));
    } finally {
      setLoading(false);
    }
  };

  const doneCount = checklist ? checklist.filter((_, i) => doneItems[i]).length : 0;

  return (
    <>
      <AgentPageHeader title={t('agents.sme-compliance-navigator.title')} />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto px-4 py-6 flex flex-col gap-4"
      >
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
            {error}
          </div>
        )}

        <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold">
              {formStep === 'review' ? t('agents.sme-compliance-navigator.review_title') : t('agents.sme-compliance-navigator.prompt')}
            </h2>
            {formStep === 'form' && (
              <div className="flex items-center rounded-full border border-zinc-200 p-0.5 text-xs dark:border-white/10">
                <button
                  type="button"
                  onClick={() => setMode('guided')}
                  className={`px-3 py-1 rounded-full font-medium transition-colors ${mode === 'guided' ? 'bg-nk-official text-white' : 'text-zinc-500 dark:text-zinc-400'}`}
                >
                  {t('agents.sme-compliance-navigator.mode_guided')}
                </button>
                <button
                  type="button"
                  onClick={() => setMode('freetext')}
                  className={`px-3 py-1 rounded-full font-medium transition-colors ${mode === 'freetext' ? 'bg-nk-official text-white' : 'text-zinc-500 dark:text-zinc-400'}`}
                >
                  {t('agents.sme-compliance-navigator.mode_freetext')}
                </button>
              </div>
            )}
          </div>

          {formStep === 'form' && mode === 'freetext' && (
            <textarea
              className="w-full border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:outline-none focus:border-nk-official dark:border-white/10 dark:placeholder:text-zinc-500"
              rows={5}
              value={businessProfile}
              onChange={(e) => setBusinessProfile(e.target.value)}
              placeholder={t('agents.sme-compliance-navigator.placeholder')}
            />
          )}

          {formStep === 'form' && mode === 'guided' && (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {t('agents.sme-compliance-navigator.business_type')}
                </span>
                <ChipSelector options={businessTypes} selected={businessType} onToggle={(id) => setBusinessType([id])} multiple={false} size="sm" />
              </div>
              <div className="flex flex-col gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {t('agents.sme-compliance-navigator.sector')}
                </span>
                <ChipSelector options={sectors} selected={sector} onToggle={(id) => setSector([id])} multiple={false} size="sm" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                    {t('agents.sme-compliance-navigator.headcount')}
                  </label>
                  <input
                    type="number"
                    min={0}
                    className="w-full border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent transition-colors focus:outline-none focus:border-nk-official dark:border-white/10"
                    value={headcount}
                    onChange={(e) => setHeadcount(e.target.value)}
                    placeholder="8"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                    {t('agents.sme-compliance-navigator.annual_revenue')}
                  </label>
                  <input
                    type="number"
                    min={0}
                    className="w-full border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent transition-colors focus:outline-none focus:border-nk-official dark:border-white/10"
                    value={annualRevenue}
                    onChange={(e) => setAnnualRevenue(e.target.value)}
                    placeholder="800000"
                  />
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {t('agents.sme-compliance-navigator.recent_events')}
                </span>
                <div className="flex flex-col gap-1.5">
                  {EVENT_OPTIONS.map((opt) => (
                    <label key={opt.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={events.includes(opt.id)}
                        onChange={() =>
                          setEvents((prev) => (prev.includes(opt.id) ? prev.filter((e) => e !== opt.id) : [...prev, opt.id]))
                        }
                        className="accent-nk-official"
                      />
                      {t(opt.labelKey)}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {formStep === 'review' && (
            // Deel-style explicit review step before submission (Mobbin
            // reference) instead of jumping straight from filling fields to
            // hitting Generate.
            <div className="rounded-xl border border-zinc-100 bg-zinc-50 p-4 text-sm text-zinc-700 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300">
              {composedProfile || <span className="text-zinc-400 dark:text-zinc-500">{t('agents.sme-compliance-navigator.empty')}</span>}
            </div>
          )}

          <div className="flex items-center justify-between gap-3">
            {formStep === 'review' ? (
              <button type="button" onClick={() => setFormStep('form')} className="text-sm text-zinc-500 dark:text-zinc-400">
                {t('agents.sme-compliance-navigator.back_to_edit')}
              </button>
            ) : (
              <span />
            )}
            {formStep === 'form' ? (
              <button
                type="button"
                disabled={!canRun}
                onClick={() => setFormStep('review')}
                className="self-end px-4 py-2 rounded-xl bg-nk-official hover:bg-nk-official-dim transition-colors text-white text-sm font-semibold disabled:opacity-50"
              >
                {t('agents.sme-compliance-navigator.review_next')}
              </button>
            ) : (
              <button
                type="button"
                disabled={loading || !canRun}
                onClick={() => void run()}
                className="self-end px-4 py-2 rounded-xl bg-nk-official hover:bg-nk-official-dim transition-colors text-white text-sm font-semibold disabled:opacity-50"
              >
                {loading ? t('agents.sme-compliance-navigator.generating') : t('agents.sme-compliance-navigator.generate')}
              </button>
            )}
          </div>
        </section>

        {loading && <AgentLoadingSkeleton message={t('agents.sme-compliance-navigator.generating')} />}

        {checklist && checklist.length > 0 && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold">{t('agents.sme-compliance-navigator.results')}</h2>
              <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                {t('agents.sme-compliance-navigator.progress').replace('{done}', String(doneCount)).replace('{total}', String(checklist.length))}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-zinc-100 dark:bg-white/10">
              <div
                className="h-1.5 rounded-full bg-nk-official transition-all"
                style={{ width: `${checklist.length ? (doneCount / checklist.length) * 100 : 0}%` }}
              />
            </div>
            <ul className="flex flex-col gap-2">
              {checklist.map((c, i) => {
                const done = Boolean(doneItems[i]);
                return (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={done}
                      onChange={() => setDoneItems((prev) => ({ ...prev, [i]: !prev[i] }))}
                      className="accent-nk-official mt-1 flex-shrink-0"
                    />
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5 ${DOMAIN_COLORS[c.domain] ?? 'bg-zinc-100 text-zinc-600 dark:bg-white/10 dark:text-zinc-300'}`}>
                      {c.label || c.domain}
                    </span>
                    <span className={done ? 'line-through text-zinc-400 dark:text-zinc-500' : ''}>{c.item}</span>
                    <span
                      className={`ml-auto flex-shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                        done
                          ? 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300'
                          : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
                      }`}
                    >
                      {done ? t('agents.sme-compliance-navigator.status_done') : t('agents.sme-compliance-navigator.status_pending')}
                    </span>
                  </li>
                );
              })}
            </ul>
            {staleWarnings.length > 0 && (
              <div className="text-xs text-amber-800 bg-amber-50 border border-amber-100 p-2 rounded-lg space-y-1 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
                {staleWarnings.map((w, i) => <p key={i}>{w}</p>)}
              </div>
            )}
          </section>
        )}

        {checklist && checklist.length === 0 && (
          <p className="text-sm text-center py-8 text-zinc-400 dark:text-zinc-500">{t('agents.sme-compliance-navigator.empty')}</p>
        )}
      </motion.div>
    </>
  );
}

export default function SmeComplianceNavigatorPage() {
  return (
    <Suspense>
      <SmeComplianceNavigatorPageInner />
    </Suspense>
  );
}
