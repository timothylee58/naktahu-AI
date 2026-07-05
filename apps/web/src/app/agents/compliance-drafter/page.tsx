'use client';

import { useCallback, useMemo, useState } from 'react';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';

type Step = 'business' | 'domains' | 'preview' | 'done';

const BUSINESS_TYPES = [
  { id: 'sole_proprietor', label: 'Sole proprietor / Peniaga tunggal' },
  { id: 'sdn_bhd', label: 'Sdn Bhd' },
  { id: 'partnership', label: 'Partnership / Perkongsian' },
];

const DOMAIN_OPTIONS = [
  { id: 'tax', label: 'Tax (LHDN)' },
  { id: 'business', label: 'Business (SSM)' },
  { id: 'epf', label: 'EPF/KWSP' },
];

export default function ComplianceDrafterPage() {
  const { t } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const [step, setStep] = useState<Step>('business');
  const [businessType, setBusinessType] = useState('sole_proprietor');
  const [domains, setDomains] = useState<string[]>(['tax', 'business', 'epf']);
  const [context, setContext] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const authHeaders = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) throw new Error('sign-in-required');
    return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  }, [supabase]);

  const toggleDomain = (id: string) => {
    setDomains((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  };

  const startAgent = async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = await authHeaders();
      const res = await fetch('/api/v1/agents/compliance-drafter/start', {
        method: 'POST',
        headers,
        body: JSON.stringify({ business_type: businessType, domains, context, language: 'bm' }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail ?? 'start-failed');
      }
      const data = (await res.json()) as { session_id: string; report_json?: Record<string, unknown> };
      setSessionId(data.session_id);
      setReport(data.report_json ?? null);
      setStep('preview');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'start-failed');
    } finally {
      setLoading(false);
    }
  };

  const confirmReport = async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const headers = await authHeaders();
      const res = await fetch('/api/v1/agents/compliance-drafter/confirm', {
        method: 'POST',
        headers,
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (!res.ok) throw new Error('confirm-failed');
      const data = (await res.json()) as { signed_url?: string };
      setDownloadUrl(data.signed_url ?? null);
      setStep('done');
    } catch {
      setError('confirm-failed');
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
        <h1 className="text-lg font-bold text-zinc-900">Compliance Drafter</h1>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-8 flex flex-col gap-6">
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2">
            {error}
          </div>
        )}

        {step === 'business' && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4">
            <h2 className="font-semibold text-zinc-900">1. Business type</h2>
            <div className="flex flex-col gap-2">
              {BUSINESS_TYPES.map((b) => (
                <label key={b.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="business"
                    checked={businessType === b.id}
                    onChange={() => setBusinessType(b.id)}
                  />
                  {b.label}
                </label>
              ))}
            </div>
            <textarea
              className="w-full border border-zinc-200 rounded-xl p-3 text-sm"
              placeholder="Additional context (optional)"
              rows={3}
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
            <button
              type="button"
              onClick={() => setStep('domains')}
              className="self-end px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold"
            >
              Next
            </button>
          </section>
        )}

        {step === 'domains' && (
          <section className="bg-white rounded-2xl border border-zinc-200 p-6 flex flex-col gap-4">
            <h2 className="font-semibold text-zinc-900">2. Compliance domains</h2>
            {DOMAIN_OPTIONS.map((d) => (
              <label key={d.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={domains.includes(d.id)}
                  onChange={() => toggleDomain(d.id)}
                />
                {d.label}
              </label>
            ))}
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setStep('business')} className="px-4 py-2 text-sm">
                Back
              </button>
              <button
                type="button"
                disabled={loading || domains.length === 0}
                onClick={() => void startAgent()}
                className="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold disabled:opacity-50"
              >
                {loading ? 'Generating…' : 'Generate preview'}
              </button>
            </div>
          </section>
        )}

        {step === 'preview' && report && (
          <section className="bg-white rounded-2xl border border-blue-200 p-6 flex flex-col gap-4">
            <h2 className="font-semibold text-zinc-900">3. Review report (HITL)</h2>
            <pre className="text-xs bg-zinc-50 border border-zinc-100 rounded-xl p-4 overflow-auto max-h-80">
              {JSON.stringify(report, null, 2)}
            </pre>
            <p className="text-xs text-zinc-500">
              Confirm to generate PDF and email delivery. 1 agent credit (RM 5) unless on Business plan.
            </p>
            <button
              type="button"
              disabled={loading}
              onClick={() => void confirmReport()}
              className="self-end px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold disabled:opacity-50"
            >
              {loading ? 'Generating PDF…' : 'Confirm & generate PDF'}
            </button>
          </section>
        )}

        {step === 'done' && (
          <section className="bg-white rounded-2xl border border-green-200 p-6 flex flex-col gap-3">
            <h2 className="font-semibold text-green-800">Report ready</h2>
            {downloadUrl ? (
              <a href={downloadUrl} className="text-blue-600 underline text-sm" target="_blank" rel="noreferrer">
                Download PDF
              </a>
            ) : (
              <p className="text-sm text-zinc-600">PDF generated — check your email if configured.</p>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
