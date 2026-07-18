'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { mapApiErrorDetail } from '@/lib/auth-headers';
import { useI18n } from '@/lib/i18n';

type Step = 'business' | 'domains' | 'preview' | 'done';

const BUSINESS_TYPES = [
  { id: 'sole_proprietor', labelKey: 'agents.compliance-drafter.business.sole' },
  { id: 'sdn_bhd', labelKey: 'agents.compliance-drafter.business.sdn' },
  { id: 'partnership', labelKey: 'agents.compliance-drafter.business.partnership' },
] as const;

const DOMAIN_OPTIONS = [
  { id: 'tax', labelKey: 'agents.compliance-drafter.domain.tax' },
  { id: 'business', labelKey: 'agents.compliance-drafter.domain.business' },
  { id: 'epf', labelKey: 'agents.compliance-drafter.domain.epf' },
] as const;

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
    <main className="min-h-screen bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-white/10 dark:bg-[#0A0F1E]/80">
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-3">
          <Link
            href="/chat"
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 transition-colors hover:text-blue-500 dark:text-blue-400 locale-nowrap"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            {t('nav.home')}
          </Link>
          <span className="text-zinc-300 dark:text-white/20" aria-hidden>/</span>
          <h1 className="text-sm font-bold">{t('agents.compliance-drafter.title')}</h1>
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

        {step === 'business' && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
            <h2 className="font-semibold">{t('agents.compliance-drafter.step1')}</h2>
            <div className="flex flex-col gap-2">
              {BUSINESS_TYPES.map((b) => (
                <label key={b.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="business"
                    checked={businessType === b.id}
                    onChange={() => setBusinessType(b.id)}
                    className="accent-blue-600"
                  />
                  {t(b.labelKey)}
                </label>
              ))}
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
              onClick={() => setStep('domains')}
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

        {step === 'preview' && report && (
          <section className="bg-white rounded-2xl border border-blue-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-blue-500/30">
            <h2 className="font-semibold">{t('agents.compliance-drafter.step3')}</h2>
            <pre className="text-xs bg-zinc-50 border border-zinc-100 rounded-xl p-4 overflow-auto max-h-80 dark:bg-black/30 dark:border-white/10 dark:text-zinc-300">
              {JSON.stringify(report, null, 2)}
            </pre>
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
          </section>
        )}
      </motion.div>
    </main>
  );
}
