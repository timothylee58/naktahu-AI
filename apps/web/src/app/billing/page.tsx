'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { NakTahuWordmark } from '@/components/logo/NakTahuWordmark';
import { effectivePlan, planBadgeLabel, userRole, ADMIN_ROLES } from '@/lib/auth-plan';
import { fetchUserCredits } from '@/lib/credits';
import { RedeemCodeCard } from '@/components/billing/RedeemCodeCard';

function fmt(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), template);
}

type ActiveGrant = { plan_tier: string; expires_at: string } | null;

export default function BillingPage() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const { supabase, user, accessToken, ready } = useSupabaseSession();
  const { get } = useAgentApi();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [credits, setCredits] = useState<number | null>(null);
  const [activeGrant, setActiveGrant] = useState<ActiveGrant>(null);

  const refreshCredits = () => {
    if (user?.id) void fetchUserCredits(supabase, user.id).then(setCredits);
  };
  const refreshPlanGrant = () => {
    void get('/api/v1/billing/plan-status').then((res) =>
      setActiveGrant((res.active_grant as ActiveGrant) ?? null),
    );
  };

  useEffect(() => {
    if (!user?.id) {
      setCredits(null);
      setActiveGrant(null);
      return;
    }
    refreshCredits();
    refreshPlanGrant();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const plan = effectivePlan(user);
  const role = userRole(user);
  const isAdmin = role ? ADMIN_ROLES.has(role) : false;
  const isUnlimited = plan === 'business' || isAdmin;

  return (
    <div className={`flex h-full ${isDark ? 'bg-[#12151C] text-white' : 'bg-zinc-50/50 text-zinc-900'}`}>
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
              <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z" clipRule="evenodd" />
            </svg>
          </button>
          <Link href="/" className="flex flex-col">
            <NakTahuWordmark markSize={20} className="text-base" />
            <span className={`text-xs ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{t('header.subtitle')}</span>
          </Link>
        </header>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="max-w-2xl mx-auto px-4 py-8 w-full flex flex-col gap-5"
        >
          <div>
            <h1 className="font-display text-lg font-bold">{t('billing.title')}</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">{t('billing.subtitle')}</p>
          </div>

          {!ready ? (
            <div className="h-32 rounded-2xl animate-pulse bg-zinc-100 dark:bg-white/5" />
          ) : !user ? (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('profile.sign_in_prompt')}</p>
            </div>
          ) : (
            <>
              {/* Plan & credits — the same two facts the JWT-driven plan
                  badge and header credits pill show elsewhere, gathered
                  into one place alongside the active-grant detail
                  (a referral/redeem-code grant, which the JWT itself
                  doesn't reflect until its next refresh — see
                  routers/billing.py::get_plan_status). */}
              <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                      {t('billing.current_plan')}
                    </span>
                    <span className="text-sm font-semibold text-nk-official-dim dark:text-nk-official">
                      {planBadgeLabel(user)}
                    </span>
                  </div>
                  <Link
                    href="/pricing"
                    className="px-4 py-2 bg-nk-official hover:bg-nk-official-dim text-white rounded-xl text-sm font-semibold transition-colors"
                  >
                    {t('billing.manage_plan')}
                  </Link>
                </div>

                <div className="border-t border-zinc-100 dark:border-white/10" />

                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                      {t('billing.credits_balance')}
                    </span>
                    <span className="text-sm font-semibold">
                      {isUnlimited
                        ? t('header.credits_unlimited')
                        : credits !== null
                          ? t('header.credits').replace('{n}', String(credits))
                          : '…'}
                    </span>
                  </div>
                  {!isUnlimited && (
                    <Link
                      href="/pricing"
                      className="px-4 py-2 border border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5 rounded-xl text-sm font-semibold transition-colors"
                    >
                      {t('billing.buy_credits')}
                    </Link>
                  )}
                </div>

                {activeGrant && (
                  <p className="text-xs font-medium text-amber-600 dark:text-amber-400">
                    {fmt(t('profile.plan_grant.active'), {
                      plan: activeGrant.plan_tier,
                      date: new Date(activeGrant.expires_at).toLocaleDateString(),
                    })}
                  </p>
                )}
              </section>

              <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col shadow-sm dark:bg-white/5 dark:border-white/10">
                <h2 className="text-sm font-semibold mb-3">{t('billing.redeem_section_title')}</h2>
                <RedeemCodeCard onCreditsGranted={refreshCredits} onPlanGranted={refreshPlanGrant} />
              </section>

              <p className="text-xs text-zinc-400 dark:text-zinc-500 text-center">
                {fmt(t('billing.support_note'), { email: 'feedback@naktahu.my' })}
              </p>
            </>
          )}
        </motion.div>
      </div>
    </div>
  );
}
