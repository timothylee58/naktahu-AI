'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { mapApiErrorDetail } from '@/lib/auth-headers';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
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

export default function SmeComplianceNavigatorPage() {
  const { t, locale } = useI18n();
  const { start } = useAgentApi();
  const [businessProfile, setBusinessProfile] = useState('');
  const [checklist, setChecklist] = useState<ChecklistItem[] | null>(null);
  const [staleWarnings, setStaleWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queryLanguage = locale === 'ms' ? 'bm' : 'en';

  const run = async () => {
    if (!businessProfile.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await start('sme-compliance-navigator', {
        business_profile: businessProfile,
        language: queryLanguage,
      });
      setChecklist((data.checklist as ChecklistItem[]) ?? []);
      setStaleWarnings((data.stale_warnings as string[]) ?? []);
    } catch (e) {
      const message = e instanceof Error ? e.message : 'start-failed';
      setError(message === 'sign-in-required' ? t('agents.error.sign_in') : mapApiErrorDetail(message, t));
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
          <h1 className="text-sm font-bold">{t('agents.sme-compliance-navigator.title')}</h1>
        </div>
      </header>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto px-4 py-8 flex flex-col gap-4"
      >
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
            {error}
          </div>
        )}

        <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
          <h2 className="font-semibold">{t('agents.sme-compliance-navigator.prompt')}</h2>
          <textarea
            className="w-full border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:outline-none focus:border-blue-400 dark:border-white/10 dark:placeholder:text-zinc-500"
            rows={5}
            value={businessProfile}
            onChange={(e) => setBusinessProfile(e.target.value)}
            placeholder={t('agents.sme-compliance-navigator.placeholder')}
          />
          <button
            type="button"
            disabled={loading || !businessProfile.trim()}
            onClick={() => void run()}
            className="self-end px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 transition-colors text-white text-sm font-semibold disabled:opacity-50"
          >
            {loading ? t('agents.sme-compliance-navigator.generating') : t('agents.sme-compliance-navigator.generate')}
          </button>
        </section>

        {loading && <AgentLoadingSkeleton message={t('agents.sme-compliance-navigator.generating')} />}

        {checklist && checklist.length > 0 && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
            <h2 className="font-semibold">{t('agents.sme-compliance-navigator.results')}</h2>
            <ul className="flex flex-col gap-2">
              {checklist.map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5 ${DOMAIN_COLORS[c.domain] ?? 'bg-zinc-100 text-zinc-600 dark:bg-white/10 dark:text-zinc-300'}`}>
                    {c.label || c.domain}
                  </span>
                  <span>{c.item}</span>
                </li>
              ))}
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
    </main>
  );
}
