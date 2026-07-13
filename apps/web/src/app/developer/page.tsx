'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { createClient } from '@/lib/supabase/client';
import { fetchWithAuth } from '@/lib/auth-headers';
import { useI18n } from '@/lib/i18n';
import { AuthButton } from '@/components/auth/AuthButton';
import { LangToggle } from '@/components/LangToggle';
import { ThemeToggle } from '@/components/ThemeToggle';

const API_BASE =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : '';

type ApiPlan = 'starter' | 'growth' | 'enterprise' | 'widget' | 'white_label';

interface ApiKeyRow {
  id: string;
  key_prefix: string;
  plan: ApiPlan;
  calls_used: number;
  calls_limit: number;
  rate_limit_per_min: number;
  domain_whitelist: string[];
  active: boolean;
  last_used_at: string | null;
  created_at: string | null;
}

interface UsageStats {
  by_domain: Record<string, number>;
  by_endpoint: Record<string, number>;
  daily: Record<string, number>;
  total_events: number;
}

const PLANS: { id: ApiPlan; price: string; desc: string }[] = [
  { id: 'starter', price: 'RM 49/mo', desc: '5,500 calls · 10 req/min · JSON + citations' },
  { id: 'growth', price: 'RM 149/mo', desc: '50,000 calls · SSE + multi-domain · 60 req/min' },
  { id: 'widget', price: 'RM 99/mo', desc: 'Embeddable widget · domain-locked key' },
  { id: 'white_label', price: 'RM 299/mo', desc: 'Widget without NakTahu branding' },
  { id: 'enterprise', price: 'Custom', desc: 'Unlimited · on-prem · custom corpus' },
];

type CodeTab = 'curl' | 'python' | 'typescript';

function CodeExamples({ apiBase, apiKeyPlaceholder }: { apiBase: string; apiKeyPlaceholder: string }) {
  const [tab, setTab] = useState<CodeTab>('curl');
  const base = apiBase || 'https://naktahu-ai-production.up.railway.app';

  const examples: Record<CodeTab, string> = {
    curl: `curl -X POST ${base}/api/v1/public/query \\
  -H "Content-Type: application/json" \\
  -H "X-NakTahu-Key: ${apiKeyPlaceholder}" \\
  -d '{"query": "Cukai pendapatan 2025?", "language": "bm"}'`,
    python: `import requests

resp = requests.post(
    "${base}/api/v1/public/query",
    headers={"X-NakTahu-Key": "${apiKeyPlaceholder}"},
    json={"query": "Cukai pendapatan 2025?", "language": "bm"},
    timeout=60,
)
data = resp.json()
print(data["answer"])`,
    typescript: `const res = await fetch("${base}/api/v1/public/query", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-NakTahu-Key": "${apiKeyPlaceholder}",
  },
  body: JSON.stringify({
    query: "Cukai pendapatan 2025?",
    language: "bm",
  }),
});
const data = await res.json();
console.log(data.answer);`,
  };

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="flex gap-2 mb-4">
        {(['curl', 'python', 'typescript'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold uppercase ${
              tab === t ? 'bg-blue-600 text-white' : 'bg-zinc-100 text-zinc-600'
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      <pre className="text-xs bg-zinc-950 text-zinc-100 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap">
        {examples[tab]}
      </pre>
      <p className="mt-3 text-xs text-zinc-500">
        <a
          href={`${base}/api/v1/public/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline"
        >
          OpenAPI docs ↗
        </a>
      </p>
    </div>
  );
}

export default function DeveloperPage() {
  const { t } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const [signedIn, setSignedIn] = useState(false);
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [plan, setPlan] = useState<ApiPlan>('starter');
  const [domains, setDomains] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newRawKey, setNewRawKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [keysRes, usageRes] = await Promise.all([
        fetchWithAuth(supabase, `${API_BASE}/api/v1/developer/keys`),
        fetchWithAuth(supabase, `${API_BASE}/api/v1/developer/usage`),
      ]);
      if (!keysRes.ok) throw new Error('keys_failed');
      if (!usageRes.ok) throw new Error('usage_failed');
      const keysData = (await keysRes.json()) as { keys: ApiKeyRow[] };
      const usageData = (await usageRes.json()) as UsageStats;
      setKeys(keysData.keys);
      setUsage(usageData);
    } catch {
      setError(t('developer.error.load'));
    } finally {
      setLoading(false);
    }
  }, [supabase, t]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSignedIn(Boolean(data.session));
      if (data.session) void load();
      else setLoading(false);
    });
  }, [supabase, load]);

  const createKey = async () => {
    setCreating(true);
    setError(null);
    setNewRawKey(null);
    try {
      const whitelist =
        plan === 'widget' || plan === 'white_label'
          ? domains
              .split(',')
              .map((d) => d.trim())
              .filter(Boolean)
          : [];
      const res = await fetchWithAuth(supabase, `${API_BASE}/api/v1/developer/keys`, {
        method: 'POST',
        body: JSON.stringify({ plan, domain_whitelist: whitelist }),
      });
      if (!res.ok) throw new Error('create_failed');
      const data = (await res.json()) as { raw_key: string; key: ApiKeyRow };
      setNewRawKey(data.raw_key);
      await load();
    } catch {
      setError(t('developer.error.create'));
    } finally {
      setCreating(false);
    }
  };

  const revokeKey = async (id: string) => {
    try {
      const res = await fetchWithAuth(supabase, `${API_BASE}/api/v1/developer/keys/${id}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('revoke_failed');
      await load();
    } catch {
      setError(t('developer.error.revoke'));
    }
  };

  const chartData = useMemo(() => {
    if (!usage?.daily) return [];
    return Object.entries(usage.daily)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-14)
      .map(([date, count]) => ({ date: date.slice(5), count }));
  }, [usage]);

  return (
    <div className="min-h-screen bg-zinc-50/50">
      <header className="border-b border-zinc-100 bg-white/90 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <Link href="/" className="font-bold text-sm text-zinc-900">
            NakTahu
          </Link>
          <div className="flex items-center gap-2">
            <ThemeToggle variant="light" />
            <LangToggle variant="light" />
            <AuthButton variant="light" />
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-10 flex flex-col gap-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">{t('developer.title')}</h1>
          <p className="mt-2 text-sm text-zinc-600 max-w-2xl">{t('developer.subtitle')}</p>
        </div>

        {!signedIn ? (
          <p className="text-sm text-zinc-500">{t('developer.sign_in')}</p>
        ) : loading ? (
          <div className="h-32 rounded-2xl bg-zinc-100 animate-pulse" />
        ) : (
          <>
            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
                {error}
              </p>
            )}

            {newRawKey && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 flex flex-col gap-2">
                <p className="text-sm font-semibold text-amber-900">{t('developer.key_once')}</p>
                <code className="text-xs bg-white border border-amber-200 rounded-lg px-3 py-2 break-all">
                  {newRawKey}
                </code>
                <button
                  type="button"
                  onClick={() => void navigator.clipboard.writeText(newRawKey)}
                  className="self-start text-xs font-semibold text-amber-800 hover:underline"
                >
                  {t('developer.copy')}
                </button>
              </div>
            )}

            <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm flex flex-col gap-4">
              <h2 className="text-sm font-semibold text-zinc-900">{t('developer.create_key')}</h2>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {PLANS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setPlan(p.id)}
                    className={`text-left rounded-xl border p-3 transition-colors ${
                      plan === p.id
                        ? 'border-blue-500 ring-1 ring-blue-500/30 bg-blue-50/50'
                        : 'border-zinc-200 hover:border-zinc-300'
                    }`}
                  >
                    <p className="text-xs font-bold uppercase text-zinc-500">{p.id}</p>
                    <p className="text-sm font-semibold text-zinc-900">{p.price}</p>
                    <p className="text-xs text-zinc-500 mt-1">{p.desc}</p>
                  </button>
                ))}
              </div>
              {(plan === 'widget' || plan === 'white_label') && (
                <input
                  type="text"
                  value={domains}
                  onChange={(e) => setDomains(e.target.value)}
                  placeholder={t('developer.domains_placeholder')}
                  className="w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm"
                />
              )}
              <button
                type="button"
                onClick={() => void createKey()}
                disabled={creating || keys.filter((k) => k.active).length >= 3}
                className="self-start rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold px-4 py-2.5 disabled:opacity-50"
              >
                {creating ? '…' : t('developer.generate')}
              </button>
            </section>

            <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-semibold text-zinc-900 mb-4">{t('developer.keys')}</h2>
              {keys.length === 0 ? (
                <p className="text-sm text-zinc-500">{t('developer.no_keys')}</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {keys.map((k) => (
                    <li
                      key={k.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-100 px-4 py-3"
                    >
                      <div>
                        <p className="text-sm font-mono font-medium text-zinc-800">
                          {k.key_prefix}…
                        </p>
                        <p className="text-xs text-zinc-500">
                          {k.plan} · {k.calls_used}/{k.calls_limit} calls · {k.rate_limit_per_min}/min
                          {!k.active && ' · revoked'}
                        </p>
                      </div>
                      {k.active && (
                        <button
                          type="button"
                          onClick={() => void revokeKey(k.id)}
                          className="text-xs font-semibold text-red-600 hover:underline"
                        >
                          {t('developer.revoke')}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {chartData.length > 0 && (
              <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
                <h2 className="text-sm font-semibold text-zinc-900 mb-4">{t('developer.usage')}</h2>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                      <Tooltip />
                      <Line type="monotone" dataKey="count" stroke="#2563EB" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>
            )}

            <CodeExamples apiBase={API_BASE} apiKeyPlaceholder="nkt_live_YOUR_KEY" />

            <section className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-semibold text-zinc-900 mb-2">{t('developer.widget')}</h2>
              <pre className="text-xs bg-zinc-950 text-zinc-100 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap">{`<script src="${typeof window !== 'undefined' ? window.location.origin : 'https://naktahu.netlify.app'}/widget.js"
  data-api-key="nkt_live_YOUR_KEY"
  data-domain="tax"
  data-lang="bm"
  data-theme="light"
  data-white-label="false"></script>`}</pre>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
