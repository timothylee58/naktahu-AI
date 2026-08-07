'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { mapApiErrorDetail } from '@/lib/auth-headers';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { useI18n } from '@/lib/i18n';

type Step = 'intake' | 'preview' | 'done';

// Same seed values as grant-finder's ChipSelector options — the backend
// does an exact string match against grant_database.eligible_sectors and
// eligibility_agent's business_type enum, not arbitrary labels.
const SECTOR_OPTIONS: ChipOption[] = [
  { id: 'technology', label: 'Technology', icon: '🖥' },
  { id: 'ai', label: 'AI', icon: '🤖' },
  { id: 'fintech', label: 'Fintech', icon: '💳' },
  { id: 'edtech', label: 'EdTech', icon: '📚' },
  { id: 'healthtech', label: 'HealthTech', icon: '⚕️' },
  { id: 'digital', label: 'Digital', icon: '📱' },
  { id: 'manufacturing', label: 'Manufacturing', icon: '🏭' },
  { id: 'services', label: 'Services', icon: '🛎' },
];

const BUSINESS_TYPE_OPTIONS: ChipOption[] = [
  { id: 'sole_prop', label: 'Sole Proprietor', icon: '🏪' },
  { id: 'sdn_bhd', label: 'Sdn Bhd', icon: '🏢' },
  { id: 'startup', label: 'Startup', icon: '🚀' },
  { id: 'llp', label: 'LLP', icon: '🤝' },
  { id: 'cooperative', label: 'Cooperative', icon: '👥' },
];

interface FinancialProjectionSkeleton {
  is_template?: boolean;
  disclaimer?: string;
  grant_amount_range_myr?: { min?: number | null; max?: number | null };
  revenue_projection?: { period?: string; projected_revenue_myr?: number | null; notes?: string }[];
  cost_breakdown?: { category?: string; amount_myr?: number | null }[];
  funding_allocation?: { use_of_funds?: string; amount_myr?: number | null }[];
}

interface DraftReport {
  executive_summary?: string;
  use_of_funds_narrative?: string;
  document_checklist?: { item?: string; required?: boolean }[];
  financial_projection_skeleton?: FinancialProjectionSkeleton;
}

function fmtMyr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '—';
  return `RM ${amount.toLocaleString()}`;
}

function GrantDraftGeneratorPageInner() {
  const { t, locale } = useI18n();
  const { start, post } = useAgentApi();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>('intake');
  const [programmeName, setProgrammeName] = useState('');
  const [businessType, setBusinessType] = useState<string[]>(['sdn_bhd']);
  const [sector, setSector] = useState<string[]>(['technology']);
  const [registeredMonths, setRegisteredMonths] = useState('');
  const [annualRevenue, setAnnualRevenue] = useState('');
  const [isBumiputera, setIsBumiputera] = useState<boolean | null>(null);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'docx'>('pdf');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [report, setReport] = useState<DraftReport | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queryLanguage = useMemo(() => (locale === 'ms' ? 'bm' : 'en'), [locale]);

  // Deep-linked from Grant Finder's results (draftLinkHref()) — prefill the
  // exact programme_name + business profile so the user doesn't retype
  // anything, and avoids typo-driven "Grant programme not found" errors
  // since fetch_grant_node does an exact string match.
  useEffect(() => {
    const programme = searchParams.get('programme');
    if (programme) setProgrammeName(programme);
    const bt = searchParams.get('business_type');
    if (bt) setBusinessType([bt]);
    const sec = searchParams.get('sector');
    if (sec) setSector([sec]);
    const months = searchParams.get('registered_months');
    if (months) setRegisteredMonths(months);
    const revenue = searchParams.get('annual_revenue_myr');
    if (revenue) setAnnualRevenue(revenue);
    const bumi = searchParams.get('is_bumiputera');
    if (bumi !== null) setIsBumiputera(bumi === 'true');
  }, [searchParams]);

  const startAgent = async () => {
    if (!programmeName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await start('grant-draft-generator', {
        programme_name: programmeName,
        business_profile: {
          business_type: businessType[0],
          sector: sector[0],
          registered_months: registeredMonths ? Number(registeredMonths) : undefined,
          annual_revenue_myr: annualRevenue ? Number(annualRevenue) : undefined,
          is_bumiputera: isBumiputera,
        },
        export_format: exportFormat,
        language: queryLanguage,
      });
      if (data.error) throw new Error(String(data.error));
      setSessionId((data.session_id as string) ?? null);
      setReport((data.output as DraftReport) ?? null);
      setStep('preview');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'start-failed';
      setError(message === 'sign-in-required' ? t('agents.error.sign_in') : mapApiErrorDetail(message, t));
    } finally {
      setLoading(false);
    }
  };

  const confirmDraft = async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await post('/api/v1/agents/grant-draft-generator/confirm', { session_id: sessionId });
      setDownloadUrl((data.signed_url as string) ?? null);
      setStep('done');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'confirm-failed';
      setError(mapApiErrorDetail(message, t));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-white/10 dark:bg-[#0A0F1E]/80">
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-3">
          <Link href="/agents" className="inline-flex items-center gap-1.5 text-sm text-blue-600 transition-colors hover:text-blue-500 dark:text-blue-400 locale-nowrap">
            <ArrowLeft className="h-4 w-4" aria-hidden />
            {t('agents.hub.title')}
          </Link>
          <span className="text-zinc-300 dark:text-white/20" aria-hidden>/</span>
          <h1 className="text-sm font-bold">{t('agents.grant-draft-generator.title')}</h1>
        </div>
      </header>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto px-4 py-8 flex flex-col gap-6"
      >
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
            {error}
          </div>
        )}

        {step === 'intake' && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
            <h2 className="font-semibold">{t('agents.grant-draft-generator.step1')}</h2>
            <input
              type="text"
              className="w-full border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:outline-none focus:border-blue-400 dark:border-white/10 dark:placeholder:text-zinc-500"
              value={programmeName}
              onChange={(e) => setProgrammeName(e.target.value)}
              placeholder={t('agents.grant-draft-generator.programme_placeholder')}
            />
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                {t('agents.grant-draft-generator.sector')}
              </span>
              <ChipSelector options={SECTOR_OPTIONS} selected={sector} onToggle={(id) => setSector([id])} multiple={false} size="sm" />
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                {t('agents.grant-draft-generator.business_type')}
              </span>
              <ChipSelector options={BUSINESS_TYPE_OPTIONS} selected={businessType} onToggle={(id) => setBusinessType([id])} multiple={false} size="sm" />
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                {t('agents.grant-draft-generator.export_format')}
              </span>
              <label className="flex items-center gap-1.5">
                <input type="radio" checked={exportFormat === 'pdf'} onChange={() => setExportFormat('pdf')} className="accent-blue-600" />
                PDF
              </label>
              <label className="flex items-center gap-1.5">
                <input type="radio" checked={exportFormat === 'docx'} onChange={() => setExportFormat('docx')} className="accent-blue-600" />
                Word (.docx)
              </label>
            </div>
            <button
              type="button"
              disabled={loading || !programmeName.trim()}
              onClick={() => void startAgent()}
              className="self-end px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors text-white text-sm font-semibold disabled:opacity-50"
            >
              {loading ? t('agents.grant-draft-generator.generating') : t('agents.grant-draft-generator.generate')}
            </button>
          </section>
        )}

        {loading && step === 'intake' && <AgentLoadingSkeleton message={t('agents.grant-draft-generator.generating')} />}

        {step === 'preview' && report && (
          <section className="bg-white rounded-2xl border border-blue-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-blue-500/30">
            <h2 className="font-semibold">{t('agents.grant-draft-generator.step2')}</h2>
            {report.executive_summary && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">
                  {t('agents.grant-draft-generator.executive_summary')}
                </h3>
                <p className="text-sm whitespace-pre-wrap">{report.executive_summary}</p>
              </div>
            )}
            {report.use_of_funds_narrative && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">
                  {t('agents.grant-draft-generator.use_of_funds')}
                </h3>
                <p className="text-sm whitespace-pre-wrap">{report.use_of_funds_narrative}</p>
              </div>
            )}
            {Array.isArray(report.document_checklist) && report.document_checklist.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">
                  {t('agents.grant-draft-generator.document_checklist')}
                </h3>
                <ul className="text-sm list-disc pl-5 space-y-1">
                  {report.document_checklist.map((d, i) => (
                    <li key={i}>{d.item}{d.required ? '' : ` (${t('agents.grant-draft-generator.optional')})`}</li>
                  ))}
                </ul>
              </div>
            )}
            {report.financial_projection_skeleton && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">
                  {t('agents.grant-draft-generator.financial_projection')}
                </h3>
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5 mb-2 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
                  {report.financial_projection_skeleton.disclaimer || t('agents.grant-draft-generator.financial_disclaimer')}
                </p>
                {report.financial_projection_skeleton.grant_amount_range_myr && (
                  <p className="text-sm mb-2">
                    <span className="text-zinc-500 dark:text-zinc-400">{t('agents.grant-draft-generator.grant_amount_range')}: </span>
                    {fmtMyr(report.financial_projection_skeleton.grant_amount_range_myr.min)} – {fmtMyr(report.financial_projection_skeleton.grant_amount_range_myr.max)}
                  </p>
                )}
                {Array.isArray(report.financial_projection_skeleton.revenue_projection) && report.financial_projection_skeleton.revenue_projection.length > 0 && (
                  <div className="mb-2">
                    <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{t('agents.grant-draft-generator.revenue_projection')}</span>
                    <ul className="text-sm list-disc pl-5 space-y-0.5">
                      {report.financial_projection_skeleton.revenue_projection.map((r, i) => (
                        <li key={i}>{r.period}: {fmtMyr(r.projected_revenue_myr)}{r.notes ? ` — ${r.notes}` : ''}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {Array.isArray(report.financial_projection_skeleton.cost_breakdown) && report.financial_projection_skeleton.cost_breakdown.length > 0 && (
                  <div className="mb-2">
                    <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{t('agents.grant-draft-generator.cost_breakdown')}</span>
                    <ul className="text-sm list-disc pl-5 space-y-0.5">
                      {report.financial_projection_skeleton.cost_breakdown.map((c, i) => (
                        <li key={i}>{c.category}: {fmtMyr(c.amount_myr)}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {Array.isArray(report.financial_projection_skeleton.funding_allocation) && report.financial_projection_skeleton.funding_allocation.length > 0 && (
                  <div>
                    <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{t('agents.grant-draft-generator.funding_allocation')}</span>
                    <ul className="text-sm list-disc pl-5 space-y-0.5">
                      {report.financial_projection_skeleton.funding_allocation.map((f, i) => (
                        <li key={i}>{f.use_of_funds}: {fmtMyr(f.amount_myr)}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('agents.grant-draft-generator.credit_note')}</p>
            <button
              type="button"
              disabled={loading}
              onClick={() => void confirmDraft()}
              className="self-end px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors text-white text-sm font-semibold disabled:opacity-50"
            >
              {loading ? t('agents.grant-draft-generator.confirming') : t('agents.grant-draft-generator.confirm')}
            </button>
          </section>
        )}

        {step === 'done' && (
          <section className="bg-white rounded-2xl border border-green-200 p-6 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-green-500/30">
            <h2 className="font-semibold text-green-800 dark:text-green-400">{t('agents.grant-draft-generator.step3')}</h2>
            {downloadUrl ? (
              <a href={downloadUrl} className="text-blue-600 underline text-sm dark:text-blue-400" target="_blank" rel="noreferrer">
                {t('agents.grant-draft-generator.download')}
              </a>
            ) : (
              <p className="text-sm text-zinc-600 dark:text-zinc-400">{t('agents.grant-draft-generator.email_hint')}</p>
            )}
            <button
              type="button"
              onClick={() => { setStep('intake'); setReport(null); setSessionId(null); setDownloadUrl(null); setProgrammeName(''); }}
              className="self-start text-sm text-blue-600 hover:underline dark:text-blue-400"
            >
              {t('agents.grant-draft-generator.new_draft')}
            </button>
          </section>
        )}
      </motion.div>
    </main>
  );
}

export default function GrantDraftGeneratorPage() {
  return (
    <Suspense>
      <GrantDraftGeneratorPageInner />
    </Suspense>
  );
}
