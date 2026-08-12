'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { mapApiErrorDetail } from '@/lib/auth-headers';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { useI18n } from '@/lib/i18n';

type Step = 'business' | 'domains' | 'preview' | 'done';

const STEP_ORDER: Step[] = ['business', 'domains', 'preview', 'done'];

const BUSINESS_TYPES = [
  { id: 'sole_proprietor', labelKey: 'agents.compliance-drafter.business.sole', icon: '🏪', desc: 'Enterprise Perseorangan' },
  { id: 'sdn_bhd', labelKey: 'agents.compliance-drafter.business.sdn', icon: '🏢', desc: 'Syarikat Sendirian Berhad' },
  { id: 'partnership', labelKey: 'agents.compliance-drafter.business.partnership', icon: '🤝', desc: 'Perkongsian / LLP' },
] as const;

const DOMAIN_OPTIONS = [
  { id: 'tax', labelKey: 'agents.compliance-drafter.domain.tax', icon: '🧾', color: 'red' },
  { id: 'business', labelKey: 'agents.compliance-drafter.domain.business', icon: '📋', color: 'blue' },
  { id: 'epf', labelKey: 'agents.compliance-drafter.domain.epf', icon: '💰', color: 'amber' },
] as const;

const DOMAIN_COLORS: Record<string, { bg: string; border: string; badge: string; text: string }> = {
  tax: {
    bg: 'bg-red-50 dark:bg-red-500/10',
    border: 'border-red-200 dark:border-red-500/30',
    badge: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
    text: 'text-red-800 dark:text-red-200',
  },
  business: {
    bg: 'bg-blue-50 dark:bg-blue-500/10',
    border: 'border-blue-200 dark:border-blue-500/30',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300',
    text: 'text-blue-800 dark:text-blue-200',
  },
  epf: {
    bg: 'bg-amber-50 dark:bg-amber-500/10',
    border: 'border-amber-200 dark:border-amber-500/30',
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
    text: 'text-amber-800 dark:text-amber-200',
  },
};

interface DomainSection {
  domain: string;
  title: string;
  items: string[];
  deadlines?: string[];
}

function parseReportSections(report: Record<string, unknown>): DomainSection[] {
  const sections: DomainSection[] = [];

  // Try to parse structured report formats
  for (const [key, value] of Object.entries(report)) {
    const lowerKey = key.toLowerCase();
    if (lowerKey === 'session_id' || lowerKey === 'status' || lowerKey === 'turns_count') continue;

    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      const obj = value as Record<string, unknown>;
      const items: string[] = [];
      const deadlines: string[] = [];

      for (const [subKey, subVal] of Object.entries(obj)) {
        if (typeof subVal === 'string' && subVal.trim()) {
          if (subKey.toLowerCase().includes('deadline') || subKey.toLowerCase().includes('tarikh')) {
            deadlines.push(subVal);
          } else {
            items.push(subVal);
          }
        } else if (Array.isArray(subVal)) {
          items.push(...subVal.filter((v): v is string => typeof v === 'string'));
        }
      }

      if (items.length > 0 || deadlines.length > 0) {
        const domain = lowerKey.includes('tax') || lowerKey.includes('cukai') ? 'tax'
          : lowerKey.includes('epf') || lowerKey.includes('kwsp') ? 'epf'
          : 'business';
        sections.push({ domain, title: key, items, deadlines });
      }
    } else if (Array.isArray(value)) {
      const items = value.filter((v): v is string => typeof v === 'string');
      if (items.length > 0) {
        const domain = lowerKey.includes('tax') ? 'tax' : lowerKey.includes('epf') ? 'epf' : 'business';
        sections.push({ domain, title: key, items });
      }
    } else if (typeof value === 'string' && value.trim().length > 20) {
      // Long string values treated as a single-item section
      const domain = lowerKey.includes('tax') ? 'tax' : lowerKey.includes('epf') ? 'epf' : 'business';
      sections.push({ domain, title: key, items: [value] });
    }
  }

  // If no structured sections found, create a single section from the entire report
  if (sections.length === 0) {
    sections.push({
      domain: 'business',
      title: 'Compliance Report',
      items: [JSON.stringify(report, null, 2)],
    });
  }

  return sections;
}

function resolveAgentError(message: string, t: (key: string) => string): string {
  if (message === 'sign-in-required') return t('agents.error.sign_in');
  if (message === 'start-failed' || message === 'agent-request-failed') {
    return t('agents.error.start_failed');
  }
  if (message === 'confirm-failed') return t('agents.error.confirm_failed');
  return mapApiErrorDetail(message, t);
}

function ComplianceDrafterPageInner() {
  const { t, locale } = useI18n();
  const { start, post, get } = useAgentApi();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>('business');
  // No default selected — this report has legal/financial consequences,
  // so a rushed "click Next without reading" shouldn't silently generate
  // a report for the wrong business type. Force an active choice instead.
  const [businessType, setBusinessType] = useState('');
  const [businessTypeTouched, setBusinessTypeTouched] = useState(false);
  const [domains, setDomains] = useState<string[]>(['tax', 'business', 'epf']);
  const [context, setContext] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queryLanguage = useMemo(() => {
    if (locale === 'ms') return 'bm';
    if (locale === 'zh') return 'en';
    return 'en';
  }, [locale]);

  const reportSections = useMemo(() => (report ? parseReportSections(report) : []), [report]);

  const toggleDomain = (id: string) => {
    setDomains((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  };

  // Resume from History's "?run=<agent_runs.id>" link — jump straight to
  // the report preview instead of the intake flow. Silent fallback to a
  // fresh intake on any failure (bad/expired link) rather than an error.
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const run = await get(`/api/v1/agent-runs/${runId}`);
        const output = (run.output as Record<string, unknown>) ?? {};
        setSessionId(typeof run.session_id === 'string' ? run.session_id : null);
        setReport((output.report_json as Record<string, unknown>) ?? output);
        setStep('preview');
      } catch {
        /* stale/invalid run id — stays on the fresh intake flow */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startAgent = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await start('compliance-drafter', {
        business_type: businessType,
        domains,
        context,
        language: queryLanguage,
      });
      setSessionId((data.session_id as string) ?? null);
      setReport((data.report_json as Record<string, unknown>) ?? null);
      setStep('preview');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'start-failed';
      setError(resolveAgentError(message, t));
    } finally {
      setLoading(false);
    }
  };

  const confirmReport = async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await post('/api/v1/agents/compliance-drafter/confirm', {
        session_id: sessionId,
      });
      setDownloadUrl((data.signed_url as string) ?? null);
      setStep('done');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'confirm-failed';
      setError(resolveAgentError(message, t));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <AgentPageHeader title={t('agents.compliance-drafter.title')} />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto px-4 py-6 flex flex-col gap-6"
      >
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
            {error}
          </div>
        )}

        {step !== 'done' && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs font-medium text-zinc-500 dark:text-zinc-400">
              <span>
                {t('agents.compliance-drafter.step_of')
                  .replace('{current}', String(STEP_ORDER.indexOf(step) + 1))
                  .replace('{total}', String(STEP_ORDER.length - 1))}
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden dark:bg-white/10">
              <div
                className="h-full rounded-full bg-blue-500 transition-all duration-300"
                style={{ width: `${((STEP_ORDER.indexOf(step) + 1) / (STEP_ORDER.length - 1)) * 100}%` }}
              />
            </div>
          </div>
        )}

        {step === 'business' && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
            <div>
              <h2 className="font-semibold">{t('agents.compliance-drafter.step1')}</h2>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                {t('agents.compliance-drafter.intro')}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              {BUSINESS_TYPES.map((b) => (
                <label key={b.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="business"
                    checked={businessType === b.id}
                    onChange={() => { setBusinessType(b.id); setBusinessTypeTouched(true); }}
                    className="accent-blue-600"
                  />
                  {t(b.labelKey)}
                </label>
              ))}
              {businessTypeTouched && !businessType && (
                <p className="text-xs text-red-600 dark:text-red-400">{t('agents.compliance-drafter.business_required')}</p>
              )}
            </div>
            <textarea
              className="w-full border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:outline-none focus:border-blue-400 dark:border-white/10 dark:placeholder:text-zinc-500"
              placeholder={t('agents.compliance-drafter.context_placeholder')}
              rows={3}
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
            <button
              type="button"
              onClick={() => {
                if (!businessType) {
                  setBusinessTypeTouched(true);
                  return;
                }
                setStep('domains');
              }}
              className="self-end px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors text-white text-sm font-semibold"
            >
              {t('agents.compliance-drafter.next')}
            </button>
          </section>
        )}

        {step === 'domains' && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
            <h2 className="font-semibold">{t('agents.compliance-drafter.step2')}</h2>
            {DOMAIN_OPTIONS.map((d) => (
              <label key={d.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={domains.includes(d.id)}
                  onChange={() => toggleDomain(d.id)}
                  className="accent-blue-600"
                />
                {t(d.labelKey)}
              </label>
            ))}
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => setStep('business')}
                className="px-4 py-2 text-sm text-zinc-600 hover:text-zinc-900 transition-colors dark:text-zinc-400 dark:hover:text-white"
              >
                {t('agents.compliance-drafter.back')}
              </button>
              <button
                type="button"
                disabled={loading || domains.length === 0}
                onClick={() => void startAgent()}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors text-white text-sm font-semibold disabled:opacity-50"
              >
                {loading ? t('agents.compliance-drafter.generating') : t('agents.compliance-drafter.generate')}
              </button>
            </div>
          </section>
        )}

        {loading && step === 'domains' && (
          <AgentLoadingSkeleton message="Menjana laporan pematuhan…" />
        )}

        {step === 'preview' && report && (
          <section className="bg-white rounded-2xl border border-blue-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-blue-500/30">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-semibold">{t('agents.compliance-drafter.step3')}</h2>
              <button
                type="button"
                onClick={() => setStep('domains')}
                className="text-xs text-zinc-500 hover:text-zinc-900 transition-colors dark:text-zinc-400 dark:hover:text-white"
              >
                {t('agents.compliance-drafter.back')}
              </button>
            </div>

            <div className="flex flex-col gap-3">
              {reportSections.map((section, i) => {
                const colors = DOMAIN_COLORS[section.domain] ?? DOMAIN_COLORS.business;
                return (
                  <details
                    key={`${section.domain}-${i}`}
                    open
                    className={`rounded-xl border p-4 ${colors.bg} ${colors.border}`}
                  >
                    <summary className="flex items-center gap-2 cursor-pointer font-semibold text-sm">
                      <span className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${colors.badge}`}>
                        {section.domain}
                      </span>
                      <span className={colors.text}>{section.title}</span>
                    </summary>
                    {section.items.length > 0 && (
                      <ul className={`mt-3 text-sm list-disc pl-5 space-y-1 ${colors.text}`}>
                        {section.items.map((line, j) => <li key={j}>{line}</li>)}
                      </ul>
                    )}
                    {section.deadlines && section.deadlines.length > 0 && (
                      <div className="mt-3 flex flex-col gap-1">
                        <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                          {t('agents.compliance-drafter.deadlines')}
                        </span>
                        <ul className="text-sm list-disc pl-5 space-y-1 text-amber-700 dark:text-amber-300">
                          {section.deadlines.map((line, j) => <li key={j}>{line}</li>)}
                        </ul>
                      </div>
                    )}
                  </details>
                );
              })}
            </div>

            <details className="text-xs">
              <summary className="cursor-pointer text-zinc-500 dark:text-zinc-400">
                {t('agents.compliance-drafter.raw_json')}
              </summary>
              <pre className="mt-2 text-xs bg-zinc-50 border border-zinc-100 rounded-xl p-4 overflow-auto max-h-80 dark:bg-black/30 dark:border-white/10 dark:text-zinc-300">
                {JSON.stringify(report, null, 2)}
              </pre>
            </details>

            <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('agents.compliance-drafter.credit_note')}</p>
            <button
              type="button"
              disabled={loading}
              onClick={() => void confirmReport()}
              className="self-end px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors text-white text-sm font-semibold disabled:opacity-50"
            >
              {loading ? t('agents.compliance-drafter.confirming') : t('agents.compliance-drafter.confirm')}
            </button>
          </section>
        )}

        {step === 'done' && (
          <section className="bg-white rounded-2xl border border-green-200 p-6 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-green-500/30">
            <h2 className="font-semibold text-green-800 dark:text-green-400">{t('agents.compliance-drafter.step4')}</h2>
            {downloadUrl ? (
              <a href={downloadUrl} className="text-blue-600 underline text-sm dark:text-blue-400" target="_blank" rel="noreferrer">
                {t('agents.compliance-drafter.download')}
              </a>
            ) : (
              <p className="text-sm text-zinc-600 dark:text-zinc-400">{t('agents.compliance-drafter.email_hint')}</p>
            )}
            <button
              type="button"
              onClick={() => { setStep('business'); setReport(null); setSessionId(null); setDownloadUrl(null); }}
              className="self-start text-sm text-blue-600 hover:underline"
            >
              ← Jana laporan baru
            </button>
          </section>
        )}
      </motion.div>
    </>
  );
}

export default function ComplianceDrafterPage() {
  return (
    <Suspense>
      <ComplianceDrafterPageInner />
    </Suspense>
  );
}
