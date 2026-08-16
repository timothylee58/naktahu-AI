'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import type { User } from '@supabase/supabase-js';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Lock } from 'lucide-react';
import { createClient } from '@/lib/supabase/client';
import { fetchWithAuth } from '@/lib/auth-headers';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { API_BASE } from '@/lib/api-base';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { canAccessPaidDeveloperPlans } from '@/lib/auth-plan';
import { AppSidebar } from '@/components/layout/AppSidebar';

type ApiPlan = 'free' | 'starter' | 'growth' | 'enterprise' | 'widget' | 'white_label';

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

const PLANS: { id: ApiPlan; price: string; desc: string; paid: boolean }[] = [
  { id: 'free', price: 'RM 0/mo', desc: '500 calls · 5 req/min · JSON + citations', paid: false },
  { id: 'starter', price: 'RM 49/mo', desc: '5,500 calls · 10 req/min · JSON + citations', paid: true },
  { id: 'growth', price: 'RM 149/mo', desc: '50,000 calls · SSE + multi-domain · 60 req/min', paid: true },
  { id: 'widget', price: 'RM 99/mo', desc: 'Embeddable widget · domain-locked key', paid: true },
  { id: 'white_label', price: 'RM 299/mo', desc: 'Widget without NakTahu branding', paid: true },
  { id: 'enterprise', price: 'Custom', desc: 'Unlimited · on-prem · custom corpus', paid: true },
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
    <Card className="p-6 shadow-[0_2px_16px_rgba(15,23,42,0.06)] transition-shadow hover:shadow-[0_4px_24px_rgba(15,23,42,0.08)]">
      <div className="flex gap-2 mb-4">
        {(['curl', 'python', 'typescript'] as const).map((tabId) => (
          <Button
            key={tabId}
            type="button"
            size="sm"
            variant={tab === tabId ? 'default' : 'secondary'}
            onClick={() => setTab(tabId)}
            className="uppercase"
          >
            {tabId}
          </Button>
        ))}
      </div>
      <pre className="text-xs bg-zinc-950 text-zinc-100 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap ring-1 ring-white/5">
        {examples[tab]}
      </pre>
      <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
        <a
          href={`${base}/api/v1/public/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-nk-official-dim hover:underline dark:text-nk-official"
        >
          OpenAPI docs ↗
        </a>
      </p>
    </Card>
  );
}

export default function DeveloperPage() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const supabase = useMemo(() => createClient(), []);
  const [signedIn, setSignedIn] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [plan, setPlan] = useState<ApiPlan>('free');
  const [domains, setDomains] = useState('');
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newRawKey, setNewRawKey] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  const canUsePaidPlans = canAccessPaidDeveloperPlans(user);

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
      setUser(data.session?.user ?? null);
      setAccessToken(data.session?.access_token ?? null);
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
    <div className={`flex h-full ${isDark ? 'bg-[#12151C]' : 'bg-zinc-50/50'}`}>
      <AppSidebar
        variant={isDark ? 'dark' : 'light'}
        isMobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        user={user}
        accessToken={accessToken}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
      />

      <div className="flex flex-col flex-1 min-w-0 h-full overflow-y-auto text-zinc-900 dark:text-white">
      <header className={`flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b backdrop-blur-md sticky top-0 z-10 shadow-sm ${
        isDark ? 'border-white/10 bg-[#12151C]/90' : 'border-zinc-100 bg-white/90'
      }`}>
        <button
          onClick={() => setSidebarOpen(true)}
          aria-label={t('header.menu')}
          className={`p-1.5 rounded-lg transition-colors lg:hidden ${
            isDark ? 'text-zinc-400 hover:bg-white/10 hover:text-zinc-200' : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800'
          }`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            <path
              fillRule="evenodd"
              d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
              clipRule="evenodd"
            />
          </svg>
        </button>
        <Link href="/" className="font-bold text-sm tracking-tight">
          NakTahu
        </Link>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-10 flex flex-col gap-8 w-full">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: 'easeOut' }}>
          <h1 className="font-display text-2xl font-bold tracking-tight">{t('developer.title')}</h1>
          <p className="mt-2 text-sm text-zinc-600 max-w-2xl leading-relaxed dark:text-zinc-400">{t('developer.subtitle')}</p>
        </motion.div>

        {!signedIn ? (
          <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
            <h2 className="text-lg font-bold text-zinc-900 dark:text-white">{t('developer.title')}</h2>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 max-w-sm">{t('developer.sign_in')}</p>
            <Link
              href="/chat"
              className="px-4 py-2 rounded-xl bg-nk-official hover:bg-nk-official-dim transition-colors text-white text-sm font-semibold"
            >
              {t('header.sign_in')}
            </Link>
          </div>
        ) : loading ? (
          <div className="flex flex-col gap-4">
            <div className="h-40 rounded-2xl bg-zinc-100 animate-pulse dark:bg-white/5" />
            <div className="h-24 rounded-2xl bg-zinc-100 animate-pulse dark:bg-white/5" />
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: 'easeOut', delay: 0.05 }}
            className="flex flex-col gap-8"
          >
            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
                {error}
              </p>
            )}

            {newRawKey && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 flex flex-col gap-2 dark:border-amber-500/30 dark:bg-amber-500/10">
                <p className="text-sm font-semibold text-amber-900 dark:text-amber-300">{t('developer.key_once')}</p>
                <code className="text-xs bg-white border border-amber-200 rounded-lg px-3 py-2 break-all dark:bg-black/30 dark:border-amber-500/30 dark:text-amber-200">
                  {newRawKey}
                </code>
                <button
                  type="button"
                  onClick={() => void navigator.clipboard.writeText(newRawKey)}
                  className="self-start text-xs font-semibold text-amber-800 hover:underline dark:text-amber-300"
                >
                  {t('developer.copy')}
                </button>
              </div>
            )}

            <Card className="p-6 shadow-[0_2px_16px_rgba(15,23,42,0.06)]">
              <div className="flex flex-col gap-4">
                <h2 className="text-sm font-semibold">{t('developer.create_key')}</h2>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {PLANS.map((p) => {
                    const locked = p.paid && !canUsePaidPlans;
                    const cardClass = `relative text-left rounded-xl border p-3 transition-all duration-200 block ${
                      plan === p.id && !locked
                        ? 'border-nk-official/40 ring-1 ring-nk-official/30 bg-nk-official/15 shadow-sm dark:bg-nk-official/10 dark:ring-nk-official/30'
                        : locked
                          ? 'border-zinc-200 opacity-70 hover:opacity-100 hover:border-zinc-300 dark:border-white/10 dark:hover:border-white/20'
                          : 'border-zinc-200 hover:border-zinc-300 hover:shadow-sm dark:border-white/10 dark:hover:border-white/20'
                    }`;
                    const cardContent = (
                      <>
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-xs font-bold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                            {p.id.replace('_', ' ')}
                          </p>
                          {!p.paid && (
                            <Badge variant="success">{t('developer.plan.free_badge')}</Badge>
                          )}
                          {locked && (
                            <Lock className="h-3.5 w-3.5 text-zinc-400 flex-shrink-0" aria-hidden />
                          )}
                        </div>
                        <p className="text-sm font-semibold">{p.price}</p>
                        <p className="text-xs text-zinc-500 mt-1 leading-relaxed dark:text-zinc-400">{p.desc}</p>
                        {locked && (
                          <p className="text-xs font-medium text-nk-official-dim dark:text-nk-official mt-2 locale-nowrap">
                            {t('developer.plan.locked')} · {t('nav.pricing')} ↗
                          </p>
                        )}
                      </>
                    );
                    return locked ? (
                      <Link key={p.id} href="/pricing" className={cardClass}>
                        {cardContent}
                      </Link>
                    ) : (
                      <button key={p.id} type="button" onClick={() => setPlan(p.id)} className={cardClass}>
                        {cardContent}
                      </button>
                    );
                  })}
                </div>
                {(plan === 'widget' || plan === 'white_label') && (
                  <Input
                    type="text"
                    value={domains}
                    onChange={(e) => setDomains(e.target.value)}
                    placeholder={t('developer.domains_placeholder')}
                  />
                )}
                <Button
                  type="button"
                  onClick={() => void createKey()}
                  disabled={creating || keys.filter((k) => k.active).length >= 3}
                  className="self-start hover:-translate-y-0.5 active:translate-y-0 shadow-blue-900/20"
                >
                  {creating ? '…' : t('developer.generate')}
                </Button>
              </div>
            </Card>

            <Card className="p-6 shadow-[0_2px_16px_rgba(15,23,42,0.06)]">
              <h2 className="text-sm font-semibold mb-4">{t('developer.keys')}</h2>
              {keys.length === 0 ? (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('developer.no_keys')}</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {keys.map((k) => (
                    <li
                      key={k.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-100 px-4 py-3 transition-colors hover:border-zinc-200 hover:bg-zinc-50/60 dark:border-white/10 dark:hover:border-white/20 dark:hover:bg-white/5"
                    >
                      <div>
                        <p className="text-sm font-mono font-medium text-zinc-800 dark:text-zinc-200">
                          {k.key_prefix}…
                        </p>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">
                          {k.plan} · {k.calls_used}/{k.calls_limit} calls · {k.rate_limit_per_min}/min
                          {!k.active && ' · revoked'}
                        </p>
                      </div>
                      {k.active && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => void revokeKey(k.id)}
                          className="text-red-600 hover:text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
                        >
                          {t('developer.revoke')}
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            {chartData.length > 0 && (
              <Card className="p-6 shadow-[0_2px_16px_rgba(15,23,42,0.06)]">
                <h2 className="text-sm font-semibold mb-4">{t('developer.usage')}</h2>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke={isDark ? 'rgba(255,255,255,0.1)' : '#e4e4e7'} />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: isDark ? '#a1a1aa' : '#71717a' }} />
                      <YAxis tick={{ fontSize: 11, fill: isDark ? '#a1a1aa' : '#71717a' }} allowDecimals={false} />
                      <Tooltip
                        contentStyle={
                          isDark
                            ? { background: '#12151C', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }
                            : undefined
                        }
                      />
                      <Line type="monotone" dataKey="count" stroke="#3B5BFF" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            <CodeExamples apiBase={API_BASE} apiKeyPlaceholder="nkt_live_YOUR_KEY" />

            <Card className="p-6 shadow-[0_2px_16px_rgba(15,23,42,0.06)]">
              <h2 className="text-sm font-semibold mb-2">{t('developer.widget')}</h2>
              <pre className="text-xs bg-zinc-950 text-zinc-100 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap ring-1 ring-white/5">{`<script src="${typeof window !== 'undefined' ? window.location.origin : 'https://naktahu.netlify.app'}/widget.js"
  data-api-key="nkt_live_YOUR_KEY"
  data-domain="tax"
  data-lang="bm"
  data-theme="light"
  data-white-label="false"></script>`}</pre>
            </Card>
          </motion.div>
        )}
      </main>
      </div>
    </div>
  );
}
