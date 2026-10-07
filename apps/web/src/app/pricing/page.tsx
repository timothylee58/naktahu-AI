'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';
import { API_BASE } from '@/lib/api-base';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { NakTahuWordmark } from '@/components/logo/NakTahuWordmark';
import { useTheme } from '@/lib/theme';
import { Badge } from '@/components/ui/badge';

type CheckoutItem =
  | 'pro_individu'
  | 'pro_individu_annual'
  | 'pro_perniagaan'
  | 'pro_perniagaan_annual'
  | 'student'
  | 'student_annual'
  | 'credits_5'
  | 'credits_20'
  | 'credits_50';

type CheckoutProvider = 'stripe' | 'hitpay';
type BillingCycle = 'monthly' | 'annual';

// Monthly RM prices (source of truth — annual figures below are derived from
// these, not independently maintained numbers). Pro/Business: 10x monthly
// ("2 months free"). Student: 3x monthly (75% off a full 12x year).
const PRO_MONTHLY = 19;
const BUSINESS_MONTHLY = 99;
const STUDENT_MONTHLY = 29;

function PlanCard({
  name,
  price,
  period,
  equivLine,
  features,
  ctaLabel,
  highlighted,
  badge,
  disabled,
  onSubscribe,
  loading,
}: {
  name: string;
  price: string;
  period: string;
  equivLine?: string;
  features: string[];
  ctaLabel: string;
  highlighted?: boolean;
  badge?: string;
  disabled?: boolean;
  onSubscribe?: () => void;
  loading?: boolean;
}) {
  return (
    <div
      className={`relative flex flex-col rounded-2xl border p-6 shadow-sm ${
        highlighted
          ? 'border-nk-official/30 ring-1 ring-nk-official/20 bg-nk-official/10 dark:border-nk-official/30 dark:ring-nk-official/20 dark:bg-nk-official/10'
          : 'border-zinc-100 ring-1 ring-zinc-900/5 bg-white dark:border-white/10 dark:ring-white/5 dark:bg-white/5'
      }`}
    >
      {badge && (
        <span className="absolute -top-3 left-6 rounded-full bg-nk-official text-white text-[11px] font-bold uppercase tracking-wide px-3 py-1 shadow-sm locale-nowrap">
          {badge}
        </span>
      )}
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">{name}</h3>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-3xl font-bold text-zinc-900 dark:text-white">{price}</span>
        <span className="text-sm text-zinc-500 dark:text-zinc-400">{period}</span>
      </div>
      {equivLine && (
        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400 locale-nowrap">{equivLine}</p>
      )}
      <ul className="mt-5 flex flex-col gap-2.5 flex-1">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm text-zinc-600 dark:text-zinc-300">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-4 h-4 flex-shrink-0 text-nk-official-dim dark:text-nk-official mt-0.5"
            >
              <path
                fillRule="evenodd"
                d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                clipRule="evenodd"
              />
            </svg>
            {f}
          </li>
        ))}
      </ul>
      <button
        onClick={onSubscribe}
        disabled={disabled || loading}
        className={`mt-6 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
          highlighted
            ? 'bg-nk-official hover:bg-nk-official-dim text-white'
            : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700 dark:bg-white/10 dark:hover:bg-white/15 dark:text-zinc-200'
        }`}
      >
        {loading ? '…' : ctaLabel}
      </button>
    </div>
  );
}

function BillingToggle({
  cycle,
  onChange,
  isDark,
}: {
  cycle: BillingCycle;
  onChange: (c: BillingCycle) => void;
  isDark: boolean;
}) {
  const { t } = useI18n();
  return (
    <div
      className={`inline-flex items-center rounded-full border p-1 ${
        isDark ? 'border-white/10 bg-white/5' : 'border-zinc-200 bg-zinc-100'
      }`}
    >
      {(['monthly', 'annual'] as const).map((c) => (
        <button
          key={c}
          type="button"
          onClick={() => onChange(c)}
          className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-colors locale-nowrap ${
            cycle === c
              ? 'bg-nk-official text-white shadow-sm'
              : isDark
                ? 'text-zinc-300 hover:text-white'
                : 'text-zinc-600 hover:text-zinc-900'
          }`}
        >
          {c === 'monthly' ? t('pricing.billing.monthly') : t('pricing.billing.annual')}
        </button>
      ))}
    </div>
  );
}

interface ComparisonRow {
  label: string;
  free: string;
  student: string;
  pro: string;
  business: string;
}

function ComparisonTable({ rows, isDark }: { rows: ComparisonRow[]; isDark: boolean }) {
  const { t } = useI18n();
  const headClass = isDark ? 'text-zinc-400 border-white/10' : 'text-zinc-500 border-zinc-200';
  const cellClass = isDark ? 'border-white/10 text-zinc-200' : 'border-zinc-100 text-zinc-700';
  return (
    <div className={`rounded-2xl border overflow-x-auto ${isDark ? 'border-white/10' : 'border-zinc-100'}`}>
      <table className="w-full text-sm border-collapse min-w-[560px]">
        <thead>
          <tr>
            <th className={`text-left font-semibold px-4 py-3 border-b ${headClass}`} aria-hidden="true"></th>
            <th className={`text-left font-semibold px-4 py-3 border-b ${headClass}`}>{t('pricing.free.name')}</th>
            <th className={`text-left font-semibold px-4 py-3 border-b ${headClass}`}>{t('pricing.student.name')}</th>
            <th className={`text-left font-semibold px-4 py-3 border-b ${headClass}`}>{t('pricing.pro.name')}</th>
            <th className={`text-left font-semibold px-4 py-3 border-b ${headClass}`}>{t('pricing.business.name')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td className={`px-4 py-3 border-b font-medium ${cellClass}`}>{row.label}</td>
              <td className={`px-4 py-3 border-b ${cellClass}`}>{row.free}</td>
              <td className={`px-4 py-3 border-b ${cellClass}`}>{row.student}</td>
              <td className={`px-4 py-3 border-b ${cellClass}`}>{row.pro}</td>
              <td className={`px-4 py-3 border-b ${cellClass}`}>{row.business}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FaqSection({ isDark }: { isDark: boolean }) {
  const { t } = useI18n();
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const items = [
    { q: t('pricing.faq.q1'), a: t('pricing.faq.a1') },
    { q: t('pricing.faq.q2'), a: t('pricing.faq.a2') },
    { q: t('pricing.faq.q3'), a: t('pricing.faq.a3') },
    { q: t('pricing.faq.q4'), a: t('pricing.faq.a4') },
    { q: t('pricing.faq.q5'), a: t('pricing.faq.a5') },
  ];
  return (
    <div className={`rounded-2xl border overflow-hidden ${isDark ? 'border-white/10' : 'border-zinc-100'}`}>
      {items.map((item, i) => {
        const open = openIdx === i;
        return (
          <div key={item.q} className={i > 0 ? `border-t ${isDark ? 'border-white/10' : 'border-zinc-100'}` : ''}>
            <button
              type="button"
              onClick={() => setOpenIdx(open ? null : i)}
              className={`w-full flex items-center justify-between gap-3 px-5 py-4 text-left text-sm font-semibold transition-colors ${
                isDark ? 'text-white hover:bg-white/5' : 'text-zinc-900 hover:bg-zinc-50'
              }`}
            >
              {item.q}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className={`w-4 h-4 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
              >
                <path
                  fillRule="evenodd"
                  d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
            {open && (
              <p className={`px-5 pb-4 text-sm leading-relaxed ${isDark ? 'text-zinc-400' : 'text-zinc-600'}`}>
                {item.a}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function PricingPage() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [pending, setPending] = useState<{ item: CheckoutItem; provider: CheckoutProvider } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [billingCycle, setBillingCycle] = useState<BillingCycle>('monthly');

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setAccessToken(data.session?.access_token ?? null);
    });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setAccessToken(session?.access_token ?? null);
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  const currentPlan = (user?.app_metadata?.plan as string | undefined) ?? 'free';

  const startCheckout = useCallback(
    async (item: CheckoutItem, provider: CheckoutProvider = 'stripe') => {
      if (!accessToken) {
        setError(t('pricing.signin_required'));
        return;
      }
      setError(null);
      setPending({ item, provider });
      try {
        const res = await fetch(`${API_BASE}/api/v1/billing/checkout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({ item, provider }),
        });
        if (!res.ok) throw new Error('checkout_failed');
        const data = (await res.json()) as { url: string };
        window.location.href = data.url;
      } catch {
        setError(t('pricing.error'));
        setPending(null);
      }
    },
    [accessToken, t],
  );

  const isPending = (item: CheckoutItem, provider: CheckoutProvider) =>
    pending?.item === item && pending?.provider === provider;

  const isAnnual = billingCycle === 'annual';

  const proPrice = isAnnual ? `RM ${PRO_MONTHLY * 10}` : `RM ${PRO_MONTHLY}`;
  const proPeriod = isAnnual ? t('pricing.period.year') : t('pricing.pro.period');
  const proEquiv = isAnnual ? t('pricing.billing.equiv').replace('{amount}', (PRO_MONTHLY * 10 / 12).toFixed(2)) : undefined;
  const proItem: CheckoutItem = isAnnual ? 'pro_individu_annual' : 'pro_individu';

  const businessPrice = isAnnual ? `RM ${BUSINESS_MONTHLY * 10}` : `RM ${BUSINESS_MONTHLY}`;
  const businessPeriod = isAnnual ? t('pricing.period.year') : t('pricing.business.period');
  const businessEquiv = isAnnual
    ? t('pricing.billing.equiv').replace('{amount}', (BUSINESS_MONTHLY * 10 / 12).toFixed(2))
    : undefined;
  const businessItem: CheckoutItem = isAnnual ? 'pro_perniagaan_annual' : 'pro_perniagaan';

  const studentPrice = isAnnual ? `RM ${STUDENT_MONTHLY * 3}` : `RM ${STUDENT_MONTHLY}`;
  const studentPeriod = isAnnual ? t('pricing.period.year') : t('pricing.student.period');
  const studentEquiv = isAnnual
    ? t('pricing.billing.equiv').replace('{amount}', (STUDENT_MONTHLY * 3 / 12).toFixed(2))
    : undefined;
  const studentItem: CheckoutItem = isAnnual ? 'student_annual' : 'student';

  const comparisonRows: ComparisonRow[] = [
    {
      label: t('pricing.table.row.questions'),
      free: t('pricing.table.value.per_day'),
      student: t('pricing.table.value.unlimited'),
      pro: t('pricing.table.value.unlimited'),
      business: t('pricing.table.value.unlimited'),
    },
    {
      label: t('pricing.table.row.context'),
      free: t('pricing.table.value.context'),
      student: t('pricing.table.value.context'),
      pro: t('pricing.table.value.context'),
      business: t('pricing.table.value.context'),
    },
    {
      label: t('pricing.table.row.domains'),
      free: t('pricing.table.value.domains_all'),
      student: t('pricing.table.value.domains_all'),
      pro: t('pricing.table.value.domains_all'),
      business: t('pricing.table.value.domains_all'),
    },
    { label: t('pricing.table.row.citations'), free: '✓', student: '✓', pro: '✓', business: '✓' },
    { label: t('pricing.table.row.voice'), free: '—', student: '—', pro: '✓', business: '✓' },
    {
      label: t('pricing.table.row.history'),
      free: '—',
      student: '—',
      pro: t('pricing.table.value.history_pro'),
      business: t('pricing.table.value.history_business'),
    },
    { label: t('pricing.table.row.deadline_agent'), free: '—', student: '—', pro: '✓', business: '✓' },
    { label: t('pricing.table.row.study_agent'), free: '—', student: '✓', pro: '—', business: '—' },
    { label: t('pricing.table.row.seats'), free: '1', student: '1', pro: '1', business: '5' },
    {
      label: t('pricing.table.row.api'),
      free: '—',
      student: '—',
      pro: '—',
      business: t('pricing.table.value.api_business'),
    },
  ];

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

      <div className="flex flex-col flex-1 min-w-0 h-full overflow-y-auto">
        <header
          className={`flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b backdrop-blur-md sticky top-0 z-10 shadow-sm ${
            isDark ? 'border-white/10 bg-[#12151C]/90 text-white' : 'border-zinc-100 bg-white/90 text-zinc-900'
          }`}
        >
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
          <Link href="/" className="flex flex-col">
            <NakTahuWordmark markSize={20} className="text-base" />
            <span className={`text-xs ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{t('header.subtitle')}</span>
          </Link>
        </header>

        <main className="max-w-5xl mx-auto px-4 py-12 w-full flex flex-col gap-14">
          <div>
            <div className="text-center mb-6">
              <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">{t('pricing.title')}</h1>
              <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">{t('pricing.subtitle')}</p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 mb-3">
              <BillingToggle cycle={billingCycle} onChange={setBillingCycle} isDark={isDark} />
            </div>

            {/* Trust signals */}
            <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1.5 mb-10 text-xs text-zinc-500 dark:text-zinc-400">
              <span className="inline-flex items-center gap-1.5 locale-nowrap">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-500">
                  <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                </svg>
                {t('pricing.trust.cancel_anytime')}
              </span>
              <span className="inline-flex items-center gap-1.5 locale-nowrap">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-500">
                  <path fillRule="evenodd" d="M10 1a4.5 4.5 0 0 0-4.5 4.5V9H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-.5V5.5A4.5 4.5 0 0 0 10 1Zm3 8V5.5a3 3 0 1 0-6 0V9h6Z" clipRule="evenodd" />
                </svg>
                {t('pricing.trust.secure_payment')}
              </span>
              <span className="inline-flex items-center gap-1.5 locale-nowrap">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-500">
                  <path d="M10.788 3.212a.75.75 0 0 0-1.576 0l-1.996 4.05-4.47.65a.75.75 0 0 0-.416 1.279l3.234 3.153-.763 4.453a.75.75 0 0 0 1.088.79L10 15.547l4.11 2.16a.75.75 0 0 0 1.088-.79l-.763-4.453 3.234-3.153a.75.75 0 0 0-.416-1.28l-4.47-.649-1.996-4.05Z" />
                </svg>
                {t('pricing.trust.official_sources')}
              </span>
            </div>

            {error && (
              <div className="max-w-md mx-auto mb-6 text-center text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2.5 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
                {error}
              </div>
            )}

            {/* 3-column core tiers */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <PlanCard
                name={t('pricing.free.name')}
                price={t('pricing.free.price')}
                period={t('pricing.free.period')}
                features={[
                  t('pricing.free.feature.1'),
                  t('pricing.free.feature.2'),
                  t('pricing.free.feature.3'),
                  t('pricing.free.feature.4'),
                ]}
                ctaLabel={t('pricing.free.cta')}
                disabled
              />
              <PlanCard
                name={t('pricing.pro.name')}
                price={proPrice}
                period={proPeriod}
                equivLine={proEquiv}
                badge={t('pricing.badge.popular')}
                features={[
                  t('pricing.pro.feature.1'),
                  t('pricing.pro.feature.2'),
                  t('pricing.pro.feature.3'),
                  t('pricing.pro.feature.4'),
                  ...(isAnnual ? [t('pricing.billing.save_pro')] : []),
                ]}
                ctaLabel={currentPlan === 'pro' ? t('pricing.free.cta') : t('pricing.pro.cta')}
                highlighted
                disabled={currentPlan === 'pro'}
                loading={isPending(proItem, 'stripe')}
                onSubscribe={() => startCheckout(proItem)}
              />
              <PlanCard
                name={t('pricing.business.name')}
                price={businessPrice}
                period={businessPeriod}
                equivLine={businessEquiv}
                features={[
                  t('pricing.business.feature.1'),
                  t('pricing.business.feature.2'),
                  t('pricing.business.feature.3'),
                  t('pricing.business.feature.4'),
                  ...(isAnnual ? [t('pricing.billing.save_pro')] : []),
                ]}
                ctaLabel={currentPlan === 'business' ? t('pricing.free.cta') : t('pricing.business.cta')}
                disabled={currentPlan === 'business'}
                loading={isPending(businessItem, 'stripe')}
                onSubscribe={() => startCheckout(businessItem)}
              />
            </div>

            {/* Student tier */}
            <div className="mt-6 flex flex-col md:flex-row items-center justify-between gap-4 rounded-2xl border border-zinc-100 ring-1 ring-zinc-900/5 bg-white p-6 dark:border-white/10 dark:ring-white/5 dark:bg-white/5">
              <div>
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-white flex items-center gap-2 flex-wrap">
                  {t('pricing.student.name')} — {studentPrice}
                  <span className="text-zinc-500 dark:text-zinc-400 font-normal">{studentPeriod}</span>
                  {isAnnual && <Badge variant="success">{t('pricing.billing.save_student')}</Badge>}
                </h3>
                {studentEquiv && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 locale-nowrap">{studentEquiv}</p>
                )}
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400 max-w-md">{t('pricing.student.desc')}</p>
              </div>
              <button
                onClick={() => startCheckout(studentItem)}
                disabled={currentPlan === 'student' || isPending(studentItem, 'stripe')}
                className="flex-shrink-0 rounded-xl px-4 py-2.5 text-sm font-semibold bg-zinc-100 hover:bg-zinc-200 text-zinc-700 dark:bg-white/10 dark:hover:bg-white/15 dark:text-zinc-200 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending(studentItem, 'stripe')
                  ? '…'
                  : currentPlan === 'student'
                    ? t('pricing.free.cta')
                    : t('pricing.student.cta')}
              </button>
            </div>

            {/* Agent credits top-up */}
            <div className="mt-6 rounded-2xl border border-zinc-100 ring-1 ring-zinc-900/5 bg-white p-6 dark:border-white/10 dark:ring-white/5 dark:bg-white/5">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">{t('pricing.credits.title')}</h3>
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('pricing.credits.subtitle')}</p>
              <div className="mt-4 flex flex-col gap-3">
                {(
                  [
                    ['credits_5', 5],
                    ['credits_20', 20],
                    ['credits_50', 50],
                  ] as const
                ).map(([item, n]) => (
                  <div
                    key={item}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-100 px-4 py-2.5 dark:border-white/10"
                  >
                    <span className="text-sm font-medium text-zinc-700 dark:text-zinc-200">
                      {n} — RM {n * 5}
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => startCheckout(item, 'stripe')}
                        disabled={isPending(item, 'stripe')}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold bg-zinc-100 hover:bg-zinc-200 text-zinc-700 dark:bg-white/10 dark:hover:bg-white/15 dark:text-zinc-200 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isPending(item, 'stripe') ? '…' : t('pricing.credits.card')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Feature comparison table */}
          <div>
            <h2 className="text-lg font-bold text-zinc-900 dark:text-white text-center mb-5">{t('pricing.table.title')}</h2>
            <ComparisonTable rows={comparisonRows} isDark={isDark} />
          </div>

          {/* FAQ */}
          <div>
            <h2 className="text-lg font-bold text-zinc-900 dark:text-white text-center mb-5">{t('pricing.faq.title')}</h2>
            <FaqSection isDark={isDark} />
          </div>
        </main>
      </div>
    </div>
  );
}
