'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';
import { AuthButton } from '@/components/auth/AuthButton';
import { LangToggle } from '@/components/LangToggle';

const API_BASE =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : '';

type CheckoutItem =
  | 'pro_individu'
  | 'pro_perniagaan'
  | 'student'
  | 'credits_5'
  | 'credits_20'
  | 'credits_50';

type CheckoutProvider = 'stripe' | 'hitpay';

function PlanCard({
  name,
  price,
  period,
  features,
  ctaLabel,
  highlighted,
  disabled,
  onSubscribe,
  loading,
}: {
  name: string;
  price: string;
  period: string;
  features: string[];
  ctaLabel: string;
  highlighted?: boolean;
  disabled?: boolean;
  onSubscribe?: () => void;
  loading?: boolean;
}) {
  return (
    <div
      className={`flex flex-col rounded-2xl border p-6 shadow-sm ${
        highlighted
          ? 'border-blue-200 ring-1 ring-blue-500/20 bg-blue-50/40'
          : 'border-zinc-100 ring-1 ring-zinc-900/5 bg-white'
      }`}
    >
      <h3 className="text-sm font-semibold text-zinc-900">{name}</h3>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-3xl font-bold text-zinc-900">{price}</span>
        <span className="text-sm text-zinc-500">{period}</span>
      </div>
      <ul className="mt-5 flex flex-col gap-2.5 flex-1">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm text-zinc-600">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-4 h-4 flex-shrink-0 text-blue-600 mt-0.5"
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
            ? 'bg-blue-600 hover:bg-blue-500 text-white'
            : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-700'
        }`}
      >
        {loading ? '…' : ctaLabel}
      </button>
    </div>
  );
}

export default function PricingPage() {
  const { t } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [pending, setPending] = useState<{ item: CheckoutItem; provider: CheckoutProvider } | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="min-h-screen bg-zinc-50/50">
      <header className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 bg-white/90 backdrop-blur-md sticky top-0 z-10 shadow-sm">
        <Link href="/" className="flex flex-col">
          <span className="text-base font-bold text-zinc-900 tracking-tight">
            {t('header.title')}
          </span>
          <span className="text-xs text-zinc-500">{t('header.subtitle')}</span>
        </Link>
        <div className="flex items-center gap-2">
          <AuthButton />
          <LangToggle variant="light" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-12">
        <div className="text-center mb-10">
          <h1 className="text-2xl font-bold text-zinc-900">{t('pricing.title')}</h1>
          <p className="mt-2 text-sm text-zinc-500">{t('pricing.subtitle')}</p>
        </div>

        {error && (
          <div className="max-w-md mx-auto mb-6 text-center text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-2.5">
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
            price={t('pricing.pro.price')}
            period={t('pricing.pro.period')}
            features={[
              t('pricing.pro.feature.1'),
              t('pricing.pro.feature.2'),
              t('pricing.pro.feature.3'),
              t('pricing.pro.feature.4'),
            ]}
            ctaLabel={currentPlan === 'pro' ? t('pricing.free.cta') : t('pricing.pro.cta')}
            highlighted
            disabled={currentPlan === 'pro'}
            loading={isPending('pro_individu', 'stripe')}
            onSubscribe={() => startCheckout('pro_individu')}
          />
          <PlanCard
            name={t('pricing.business.name')}
            price={t('pricing.business.price')}
            period={t('pricing.business.period')}
            features={[
              t('pricing.business.feature.1'),
              t('pricing.business.feature.2'),
              t('pricing.business.feature.3'),
              t('pricing.business.feature.4'),
            ]}
            ctaLabel={currentPlan === 'business' ? t('pricing.free.cta') : t('pricing.business.cta')}
            disabled={currentPlan === 'business'}
            loading={isPending('pro_perniagaan', 'stripe')}
            onSubscribe={() => startCheckout('pro_perniagaan')}
          />
        </div>

        {/* Student tier */}
        <div className="mt-6 flex flex-col md:flex-row items-center justify-between gap-4 rounded-2xl border border-zinc-100 ring-1 ring-zinc-900/5 bg-white p-6">
          <div>
            <h3 className="text-sm font-semibold text-zinc-900">
              {t('pricing.student.name')} — {t('pricing.student.price')}
              <span className="text-zinc-500 font-normal">{t('pricing.student.period')}</span>
            </h3>
            <p className="mt-1 text-sm text-zinc-500 max-w-md">{t('pricing.student.desc')}</p>
          </div>
          <button
            onClick={() => startCheckout('student')}
            disabled={currentPlan === 'student' || isPending('student', 'stripe')}
            className="flex-shrink-0 rounded-xl px-4 py-2.5 text-sm font-semibold bg-zinc-100 hover:bg-zinc-200 text-zinc-700 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending('student', 'stripe')
              ? '…'
              : currentPlan === 'student'
                ? t('pricing.free.cta')
                : t('pricing.student.cta')}
          </button>
        </div>

        {/* Agent credits top-up */}
        <div className="mt-6 rounded-2xl border border-zinc-100 ring-1 ring-zinc-900/5 bg-white p-6">
          <h3 className="text-sm font-semibold text-zinc-900">{t('pricing.credits.title')}</h3>
          <p className="mt-1 text-sm text-zinc-500">{t('pricing.credits.subtitle')}</p>
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
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-zinc-100 px-4 py-2.5"
              >
                <span className="text-sm font-medium text-zinc-700">
                  {n} — RM {n * 5}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => startCheckout(item, 'stripe')}
                    disabled={isPending(item, 'stripe')}
                    className="rounded-lg px-3 py-1.5 text-xs font-semibold bg-zinc-100 hover:bg-zinc-200 text-zinc-700 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isPending(item, 'stripe') ? '…' : t('pricing.credits.card')}
                  </button>
                  <button
                    onClick={() => startCheckout(item, 'hitpay')}
                    disabled={isPending(item, 'hitpay')}
                    className="rounded-lg px-3 py-1.5 text-xs font-semibold bg-teal-50 hover:bg-teal-100 text-teal-700 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isPending(item, 'hitpay') ? '…' : t('pricing.credits.fpx')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
