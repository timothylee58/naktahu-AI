'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
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

interface DraftReport {
  executive_summary?: string;
  use_of_funds_narrative?: string;
  document_checklist?: { item?: string; required?: boolean }[];
}

export default function GrantDraftGeneratorPage() {
  const { t, locale } = useI18n();
  const { start, post } = useAgentApi();
  const [step, setStep] = useState<Step>('intake');
  const [programmeName, setProgrammeName] = useState('');
  const [businessType, setBusinessType] = useState<string[]>(['sdn_bhd']);
  const [sector, setSector] = useState<string[]>(['technology']);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'docx'>('pdf');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [report, setReport] = useState<DraftReport | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queryLanguage = useMemo(() => (locale === 'ms' ? 'bm' : 'en'), [locale]);

  const startAgent = async () => {
    if (!programmeName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await start('grant-draft-generator', {
        programme_name: programmeName,
        business_profile: { business_type: businessType[0], sector: sector[0] },
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
