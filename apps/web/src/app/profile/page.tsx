'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { effectivePlan, planBadgeLabel, userRole, ADMIN_ROLES } from '@/lib/auth-plan';
import { fetchUserCredits } from '@/lib/credits';
import { suggestForQuery } from '@/lib/agent-suggestions';
import { SuggestionCard } from '@/components/agents/SuggestionCard';

const FEEDBACK_EMAIL = 'feedback@naktahu.my';

function fmt(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), template);
}

type RedeemStatus =
  | { kind: 'idle' }
  | { kind: 'success'; message: string }
  | { kind: 'error'; message: string };

export default function ProfilePage() {
  const { t } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const { supabase, user, accessToken, ready } = useSupabaseSession();
  const { get, post } = useAgentApi();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [credits, setCredits] = useState<number | null>(null);
  const [suggestQuery, setSuggestQuery] = useState('');

  const [referralCode, setReferralCode] = useState<string | null>(null);
  const [completedReferrals, setCompletedReferrals] = useState(0);
  const [copyLabel, setCopyLabel] = useState<'copy' | 'copied' | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);

  const [redeemInput, setRedeemInput] = useState('');
  const [redeemLoading, setRedeemLoading] = useState(false);
  const [redeemStatus, setRedeemStatus] = useState<RedeemStatus>({ kind: 'idle' });
  const [activeGrant, setActiveGrant] = useState<{ plan_tier: string; expires_at: string } | null>(null);

  useEffect(() => {
    if (!user?.id) {
      setCredits(null);
      return;
    }
    let active = true;
    void fetchUserCredits(supabase, user.id).then((c) => {
      if (active) setCredits(c);
    });
    return () => {
      active = false;
    };
  }, [user?.id, supabase]);

  useEffect(() => {
    if (!user?.id) {
      setReferralCode(null);
      setActiveGrant(null);
      return;
    }
    let active = true;
    void get('/api/v1/referrals/me').then((res) => {
      if (!active) return;
      setReferralCode(typeof res.code === 'string' ? res.code : null);
      setCompletedReferrals(Number(res.completed_referrals ?? 0));
    }).catch(() => {
      /* referrals temporarily unavailable — card degrades to a loading skeleton */
    });
    void get('/api/v1/billing/plan-status').then((res) => {
      if (!active) return;
      const grant = res.active_grant as { plan_tier: string; expires_at: string } | null;
      setActiveGrant(grant ?? null);
    }).catch(() => {
      /* best-effort — plan badge elsewhere still reflects the JWT plan */
    });
    return () => {
      active = false;
    };
  }, [user?.id, get]);

  const referralLink = referralCode
    ? `https://naktahu.my/?ref=${encodeURIComponent(referralCode)}`
    : '';

  const copyReferralCode = () => {
    if (!referralCode) return;
    void navigator.clipboard.writeText(referralCode).then(() => {
      setCopyLabel('copied');
      setTimeout(() => setCopyLabel(null), 2000);
    });
  };

  const copyReferralLink = () => {
    if (!referralLink) return;
    void navigator.clipboard.writeText(referralLink).then(() => {
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    });
  };

  const shareViaWhatsApp = () => {
    if (!referralCode) return;
    const message = fmt(t('profile.referral.whatsapp_message'), { code: referralCode, link: referralLink });
    window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, '_blank', 'noopener,noreferrer');
  };

  const submitRedeemCode = async () => {
    const code = redeemInput.trim();
    if (!code) return;
    setRedeemLoading(true);
    setRedeemStatus({ kind: 'idle' });
    try {
      const res = await post('/api/v1/billing/redeem', { code });
      if (res.status === 'credits_granted') {
        setRedeemStatus({ kind: 'success', message: fmt(t('profile.redeem.status.credits_granted'), { n: Number(res.credits_amount) }) });
        void fetchUserCredits(supabase, user!.id).then(setCredits);
      } else if (res.status === 'plan_granted') {
        setRedeemStatus({
          kind: 'success',
          message: fmt(t('profile.redeem.status.plan_granted'), { plan: String(res.plan_tier), days: Number(res.duration_days) }),
        });
        void get('/api/v1/billing/plan-status').then((r) => setActiveGrant((r.active_grant as { plan_tier: string; expires_at: string } | null) ?? null));
      } else {
        setRedeemStatus({ kind: 'error', message: t('profile.redeem.status.error') });
      }
      setRedeemInput('');
    } catch (e) {
      const detail = e instanceof Error ? e.message : '';
      const key = `profile.redeem.status.${detail.replace(/\s+/g, '_')}`;
      const resolved = t(key);
      setRedeemStatus({ kind: 'error', message: resolved === key ? t('profile.redeem.status.error') : resolved });
    } finally {
      setRedeemLoading(false);
    }
  };

  const suggestions = useMemo(() => suggestForQuery(suggestQuery), [suggestQuery]);
  const plan = effectivePlan(user);
  const role = userRole(user);
  const isAdmin = role ? ADMIN_ROLES.has(role) : false;

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
            <span className="text-base font-bold tracking-tight">{t('header.title')}</span>
            <span className={`text-xs ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{t('header.subtitle')}</span>
          </Link>
        </header>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="max-w-2xl mx-auto px-4 py-8 w-full flex flex-col gap-5"
        >
          <h1 className="text-lg font-bold">{t('profile.title')}</h1>

          {!ready ? (
            <div className="h-32 rounded-2xl animate-pulse bg-zinc-100 dark:bg-white/5" />
          ) : !user ? (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('profile.sign_in_prompt')}</p>
            </div>
          ) : (
            <>
              <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex items-center gap-4 shadow-sm dark:bg-white/5 dark:border-white/10">
                {user.user_metadata?.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={user.user_metadata.avatar_url as string}
                    alt="avatar"
                    className="w-14 h-14 rounded-full border border-zinc-200"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="w-14 h-14 rounded-full bg-nk-official flex items-center justify-center text-white text-xl font-bold">
                    {(user.email ?? 'U')[0].toUpperCase()}
                  </div>
                )}
                <div className="flex flex-col gap-1.5 min-w-0">
                  <p className="text-sm font-medium truncate">{user.email}</p>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[10px] font-semibold uppercase tracking-wide bg-nk-official/10 text-nk-official-dim rounded-full px-2 py-0.5 dark:bg-nk-official/20 dark:text-nk-official">
                      {planBadgeLabel(user)}
                    </span>
                    <span className="text-[10px] font-medium text-zinc-500 dark:text-zinc-400">
                      {plan === 'business' || isAdmin
                        ? t('header.credits_unlimited')
                        : credits !== null
                          ? t('header.credits').replace('{n}', String(credits))
                          : '…'}
                    </span>
                    {activeGrant && (
                      <span className="text-[10px] font-medium text-amber-600 dark:text-amber-400">
                        {fmt(t('profile.plan_grant.active'), {
                          plan: activeGrant.plan_tier,
                          date: new Date(activeGrant.expires_at).toLocaleDateString(),
                        })}
                      </span>
                    )}
                  </div>
                </div>
              </section>

              <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                  {t('profile.feedback.title')}
                </span>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('profile.feedback.desc')}</p>
                <a
                  href={`mailto:${FEEDBACK_EMAIL}`}
                  className="self-start px-4 py-2 bg-nk-official/10 hover:bg-nk-official/20 text-nk-official-dim dark:text-nk-official rounded-full text-sm font-semibold transition-colors"
                >
                  {t('profile.feedback.button')}
                </a>
              </section>

              <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
                <h2 className="text-sm font-semibold">{t('profile.referral.title')}</h2>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('profile.referral.desc')}</p>

                {referralCode ? (
                  <>
                    <div className="flex items-center justify-between gap-2 border border-dashed border-nk-official/40 rounded-xl px-4 py-2.5">
                      <span className="font-mono font-bold tracking-widest text-nk-official-dim dark:text-nk-official">
                        {referralCode}
                      </span>
                      <button
                        type="button"
                        onClick={copyReferralCode}
                        className="text-xs font-medium text-zinc-500 hover:text-nk-official-dim dark:text-zinc-400 dark:hover:text-nk-official transition-colors"
                      >
                        {copyLabel === 'copied' ? t('profile.referral.copied') : t('profile.referral.copy')}
                      </button>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={shareViaWhatsApp}
                        className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-xl text-sm font-semibold transition-colors"
                      >
                        {t('profile.referral.whatsapp')}
                      </button>
                      <button
                        type="button"
                        onClick={copyReferralLink}
                        className="flex-1 px-3 py-2 border border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5 rounded-xl text-sm font-semibold transition-colors"
                      >
                        {linkCopied ? t('profile.referral.link_copied') : t('profile.referral.link')}
                      </button>
                    </div>
                    <p className="text-xs text-zinc-400 dark:text-zinc-500">
                      {fmt(t('profile.referral.completed_count'), { n: completedReferrals })}
                    </p>
                  </>
                ) : (
                  <div className="h-20 rounded-xl animate-pulse bg-zinc-100 dark:bg-white/5" />
                )}
              </section>

              <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
                <h2 className="text-sm font-semibold">{t('profile.redeem.title')}</h2>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('profile.redeem.desc')}</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={redeemInput}
                    onChange={(e) => setRedeemInput(e.target.value.toUpperCase())}
                    placeholder={t('profile.redeem.placeholder')}
                    className="flex-1 border border-zinc-200 rounded-xl p-2.5 text-sm font-mono tracking-wide bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-500"
                  />
                  <button
                    type="button"
                    disabled={redeemLoading || !redeemInput.trim()}
                    onClick={() => void submitRedeemCode()}
                    className="px-4 py-2 bg-nk-official hover:bg-nk-official-dim text-white rounded-xl text-sm font-semibold transition-colors disabled:opacity-50"
                  >
                    {t('profile.redeem.button')}
                  </button>
                </div>
                {redeemStatus.kind !== 'idle' && (
                  <p
                    className={`text-xs font-medium ${
                      redeemStatus.kind === 'success'
                        ? 'text-green-600 dark:text-green-400'
                        : 'text-red-600 dark:text-red-400'
                    }`}
                  >
                    {redeemStatus.message}
                  </p>
                )}
              </section>

              {/* Smart suggestions — rule-based, no LLM call. Full experience
                  here; a condensed version of the same engine lives in the
                  sidebar's profile-card popover (AuthButton, layout="sidebar"). */}
              <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
                <h2 className="text-sm font-semibold">{t('profile.suggestions_title')}</h2>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('profile.suggestions_desc')}</p>
                <input
                  type="text"
                  value={suggestQuery}
                  onChange={(e) => setSuggestQuery(e.target.value)}
                  placeholder={t('profile.suggestions_placeholder')}
                  className="w-full border border-zinc-200 rounded-xl p-3 text-sm bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-500"
                />
                {suggestQuery.trim() && (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {suggestions.map((s, i) => (
                      <SuggestionCard key={i} suggestion={s} />
                    ))}
                  </div>
                )}
              </section>

              <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-2 shadow-sm dark:bg-white/5 dark:border-white/10">
                <h2 className="text-sm font-semibold">{t('profile.quick_links_title')}</h2>
                <div className="flex flex-wrap gap-2">
                  <Link href="/history" className="text-xs font-medium px-3 py-1.5 rounded-full border border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5 transition-colors">
                    {t('history.title')}
                  </Link>
                  <Link href="/developer" className="text-xs font-medium px-3 py-1.5 rounded-full border border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5 transition-colors">
                    {t('nav.developer')}
                  </Link>
                  <Link href="/pricing" className="text-xs font-medium px-3 py-1.5 rounded-full border border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5 transition-colors">
                    {t('nav.pricing')}
                  </Link>
                  <Link href="/agents" className="text-xs font-medium px-3 py-1.5 rounded-full border border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5 transition-colors">
                    {t('nav.agents')}
                  </Link>
                </div>
              </section>
            </>
          )}
        </motion.div>
      </div>
    </div>
  );
}
