'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { mapApiErrorDetail } from '@/lib/auth-headers';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { useI18n } from '@/lib/i18n';

type Step = 'business' | 'domains' | 'preview' | 'done';

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
  tax: { bg: 'bg-red-50', border: 'border-red-200', badge: 'bg-red-100 text-red-700', text: 'text-red-800' },
  business: { bg: 'bg-blue-50', border: 'border-blue-200', badge: 'bg-blue-100 text-blue-700', text: 'text-blue-800' },
  epf: { bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-100 text-amber-700', text: 'text-amber-800' },
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

export default function ComplianceDrafterPage() {
  const { t, locale } = useI18n();
  const { start, post } = useAgentApi();
  const [step, setStep] = useState<Step>('business');
  const [businessType, setBusinessType] = useState('sole_proprietor');
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

  const toggleDomain = (id: string) => {
    setDomains((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  };

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
    <main className="min-h-screen bg-zinc-50">
      <header className="bg-white border-b border-zinc-200 px-4 py-3 flex items-center gap-3">
        <Link href="/chat" className="text-sm text-blue-600 hover:underline">
          ← {t('nav.home')}
        </Link>
        <h1 className="text-lg font-bold text-zinc-900">{t('agents.compliance-drafter.title')}</h1>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-8 flex flex-col gap-6">
        {/* Step progress indicator */}
        <div className="flex items-center justify-center gap-2">
          {(['business', 'domains', 'preview', 'done'] as Step[]).map((s, i) => {
            const stepLabels = ['1', '2', '3', '✓'];
            const isActive = s === step;
            const isPast = ['business', 'domains', 'preview', 'done'].indexOf(step) > i;
            return (
              <div key={s} className="flex items-center gap-2">
                <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                  isActive ? 'bg-blue-600 text-white' : isPast ? 'bg-blue-100 text-blue-600' : 'bg-zinc-100 text-zinc-400'
                }`}>
                  {stepLabels[i]}
                </div>
                {i < 3 && <div className={`h-0.5 w-6 rounded ${isPast ? 'bg-blue-300' : 'bg-zinc-200'}`} />}
              </div>
            );
          })}
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2">
            {error}
          </div>
        )}

        {step === 'business' && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4">
            <h2 className="font-semibold text-zinc-900">{t('agents.compliance-drafter.step1')}</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              {BUSINESS_TYPES.map((b) => (
                <button
                  key={b.id}
                  type="button"
                  onClick={() => setBusinessType(b.id)}
                  className={`flex flex-col items-center gap-2 rounded-xl border-2 p-4 text-center transition-all ${
                    businessType === b.id
                      ? 'border-blue-500 bg-blue-50 shadow-sm'
                      : 'border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50'
                  }`}
                >
                  <span className="text-2xl" aria-hidden>{b.icon}</span>
                  <span className="text-sm font-medium text-zinc-900">{t(b.labelKey)}</span>
                  <span className="text-[11px] text-zinc-500">{b.desc}</span>
                </button>
              ))}
            </div>
            <textarea
              className="w-full border border-zinc-200 rounded-xl p-3 text-sm placeholder:text-zinc-400 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-100"
              placeholder={t('agents.compliance-drafter.context_placeholder')}
              rows={3}
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
            <button
              type="button"
              onClick={() => setStep('domains')}
              className="self-end px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold transition-colors hover:bg-blue-700"
            >
              {t('agents.compliance-drafter.next')}
            </button>
          </section>
        )}

        {step === 'domains' && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4">
            <h2 className="font-semibold text-zinc-900">{t('agents.compliance-drafter.step2')}</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              {DOMAIN_OPTIONS.map((d) => {
                const isSelected = domains.includes(d.id);
                const colors = DOMAIN_COLORS[d.id] ?? DOMAIN_COLORS.business;
                return (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => toggleDomain(d.id)}
                    className={`flex items-center gap-3 rounded-xl border-2 p-4 transition-all ${
                      isSelected
                        ? `${colors.border} ${colors.bg} shadow-sm`
                        : 'border-zinc-200 bg-white hover:border-zinc-300'
                    }`}
                  >
                    <span className="text-xl" aria-hidden>{d.icon}</span>
                    <div className="text-left">
                      <span className="text-sm font-medium text-zinc-900">{t(d.labelKey)}</span>
                      {isSelected && <span className="ml-2 text-xs text-blue-600">✓</span>}
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setStep('business')} className="px-4 py-2 text-sm text-zinc-600 hover:text-zinc-900">
                {t('agents.compliance-drafter.back')}
              </button>
              <button
                type="button"
                disabled={loading || domains.length === 0}
                onClick={() => void startAgent()}
                className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold disabled:opacity-50 transition-colors hover:bg-blue-700"
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
          <section className="bg-white rounded-2xl border border-blue-200 p-6 flex flex-col gap-5">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-zinc-900 flex items-center gap-2">
                <span aria-hidden>📋</span>
                {t('agents.compliance-drafter.step3')}
              </h2>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                Preview
              </span>
            </div>

            {/* Structured domain sections */}
            <div className="flex flex-col gap-4">
              {parseReportSections(report).map((section, idx) => {
                const colors = DOMAIN_COLORS[section.domain] ?? DOMAIN_COLORS.business;
                return (
                  <div key={idx} className={`rounded-xl border ${colors.border} ${colors.bg} p-4 flex flex-col gap-2`}>
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${colors.badge}`}>
                        {section.domain.toUpperCase()}
                      </span>
                      <h3 className={`text-sm font-semibold ${colors.text}`}>
                        {section.title.replace(/_/g, ' ')}
                      </h3>
                    </div>
                    <ul className="space-y-1.5 ml-1">
                      {section.items.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-zinc-700">
                          <span className="mt-0.5 text-xs">•</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                    {section.deadlines && section.deadlines.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-2">
                        {section.deadlines.map((dl, i) => (
                          <span key={i} className="inline-flex items-center gap-1 rounded-lg bg-white/70 px-2 py-1 text-xs font-medium text-zinc-700 border border-zinc-200">
                            📅 {dl}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="flex items-center justify-between border-t border-zinc-200 pt-4">
              <p className="text-xs text-zinc-500">{t('agents.compliance-drafter.credit_note')}</p>
              <button
                type="button"
                disabled={loading}
                onClick={() => void confirmReport()}
                className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold disabled:opacity-50 transition-colors hover:bg-blue-700"
              >
                {loading ? t('agents.compliance-drafter.confirming') : t('agents.compliance-drafter.confirm')}
              </button>
            </div>
          </section>
        )}

        {step === 'done' && (
          <section className="bg-white rounded-2xl border border-green-200 p-6 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
                <span className="text-lg" aria-hidden>✓</span>
              </div>
              <div>
                <h2 className="font-semibold text-green-800">{t('agents.compliance-drafter.step4')}</h2>
                <p className="text-xs text-zinc-500">Laporan PDF anda telah dijana</p>
              </div>
            </div>
            {downloadUrl ? (
              <a
                href={downloadUrl}
                className="flex items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-5 py-3 text-sm font-semibold text-blue-700 transition-colors hover:bg-blue-100"
                target="_blank"
                rel="noreferrer"
              >
                📄 {t('agents.compliance-drafter.download')}
              </a>
            ) : (
              <p className="text-sm text-zinc-600 bg-zinc-50 rounded-xl px-4 py-3">{t('agents.compliance-drafter.email_hint')}</p>
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
      </div>
    </main>
  );
}
