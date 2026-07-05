'use client';

import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { fetchWithAuth } from '@/lib/auth-headers';
import { effectivePlan, planBadgeLabel } from '@/lib/auth-plan';
import { useI18n } from '@/lib/i18n';

type Tab = 'options' | 'email';

interface AuthButtonProps {
  /** Skeleton + dropdown hover styles for dark (landing) vs light (chat) headers */
  variant?: 'dark' | 'light';
  /** sidebar = full-width register/login in left panel */
  layout?: 'compact' | 'sidebar';
}

const ANON_SESSION_KEY = 'naktahu_anon_session_id';

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function AuthButton({ variant = 'light', layout = 'compact' }: AuthButtonProps) {
  const { t } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>('options');
  const [email, setEmail] = useState('');
  const [emailSent, setEmailSent] = useState(false);
  const [signingIn, setSigningIn] = useState<'google' | 'microsoft' | 'email' | null>(null);
  const [credits, setCredits] = useState<number | null>(null);

  useEffect(() => {
    if (!localStorage.getItem(ANON_SESSION_KEY)) {
      localStorage.setItem(ANON_SESSION_KEY, generateUUID());
    }
  }, []);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setLoading(false);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      setUser(session?.user ?? null);
      if (session?.user) {
        // Migrate anonymous history to authenticated account
        const anonId = localStorage.getItem(ANON_SESSION_KEY);
        if (anonId) {
          try {
            const apiBase = process.env.NEXT_PUBLIC_API_URL ?? '';
            await fetch(`${apiBase}/api/v1/session/migrate`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${session.access_token}`,
              },
              body: JSON.stringify({ anonymous_id: anonId }),
            });
            localStorage.removeItem(ANON_SESSION_KEY);
          } catch {
            // Non-critical — don't block sign-in
          }
        }
      }
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  useEffect(() => {
    if (!user) {
      setCredits(null);
      return;
    }
    let active = true;
    void (async () => {
      try {
        const res = await fetchWithAuth(supabase, '/api/v1/billing/credits');
        if (!res.ok || !active) return;
        const data = (await res.json()) as { credits_remaining: number };
        if (active) setCredits(data.credits_remaining);
      } catch {
        // Non-critical — badge just won't show a credit count
      }
    })();
    return () => {
      active = false;
    };
  }, [user, supabase]);

  const openModal = () => { setOpen(true); setTab('options'); setEmailSent(false); setEmail(''); };
  const closeModal = () => { setOpen(false); };

  const signInWithGoogle = async () => {
    setSigningIn('google');
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) setSigningIn(null);
  };

  const signInWithMicrosoft = async () => {
    setSigningIn('microsoft');
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'azure',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        // Azure must return an email claim — see infra/supabase/AUTH_SETUP.md
        scopes: 'email openid profile offline_access',
      },
    });
    if (error) setSigningIn(null);
  };

  const signInWithEmail = async () => {
    if (!email) return;
    setSigningIn('email');
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setSigningIn(null);
    if (!error) setEmailSent(true);
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    localStorage.setItem(ANON_SESSION_KEY, generateUUID());
  };

  const skeletonClass =
    variant === 'dark'
      ? 'bg-white/10 animate-pulse'
      : 'bg-zinc-200 animate-pulse';

  const isSidebar = layout === 'sidebar';

  if (loading) {
    return (
      <div
        className={`${isSidebar ? 'w-full h-10' : 'w-24 h-8'} rounded-xl ${skeletonClass}`}
      />
    );
  }

  if (user) {
    const plan = effectivePlan(user);
    const creditsLabel =
      plan === 'business'
        ? t('header.credits_unlimited')
        : credits !== null
          ? t('header.credits').replace('{n}', String(credits))
          : null;

    if (isSidebar) {
      return (
        <div className="w-full flex flex-col gap-2">
          <div className={`flex flex-col gap-2 rounded-xl px-3 py-2.5 border ${variant === 'dark' ? 'border-white/10 bg-white/5' : 'border-zinc-200 bg-zinc-50'}`}>
            <div className="flex items-center gap-2 min-w-0">
              {user.user_metadata?.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.user_metadata.avatar_url as string}
                  alt="avatar"
                  className="w-8 h-8 rounded-full border border-zinc-200 flex-shrink-0"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                  {(user.email ?? 'U')[0].toUpperCase()}
                </div>
              )}
              <span className={`text-xs font-medium truncate min-w-0 ${variant === 'dark' ? 'text-zinc-300' : 'text-zinc-600'}`}>
                {user.email}
              </span>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className={`text-[10px] font-semibold uppercase tracking-wide rounded-full px-2 py-0.5 ${variant === 'dark' ? 'bg-blue-500/20 text-blue-200' : 'bg-blue-50 text-blue-700'}`}>
                {planBadgeLabel(user)}
              </span>
              {creditsLabel && (
                <span className={`text-[10px] font-medium ${variant === 'dark' ? 'text-zinc-400' : 'text-zinc-500'}`}>
                  {creditsLabel}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={signOut}
            className={`w-full text-sm font-medium rounded-xl px-4 py-2.5 transition-colors locale-nowrap ${variant === 'dark' ? 'text-zinc-300 hover:bg-white/10 border border-white/10' : 'text-zinc-700 hover:bg-zinc-100 border border-zinc-200'}`}
          >
            {t('header.sign_out')}
          </button>
        </div>
      );
    }

    return (
      <div className="relative">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-full px-3 py-1.5 hover:bg-zinc-100 transition-colors"
        >
          {user.user_metadata?.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={user.user_metadata.avatar_url as string}
              alt="avatar"
              className="w-7 h-7 rounded-full border border-zinc-200"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
              {(user.email ?? 'U')[0].toUpperCase()}
            </div>
          )}
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3 text-zinc-400">
            <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
          </svg>
        </button>
        <AnimatePresence>
          {open && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
              <motion.div
                initial={{ opacity: 0, y: -6, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.96 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 mt-2 w-52 bg-white border border-zinc-100 rounded-2xl shadow-xl z-50 overflow-hidden ring-1 ring-zinc-900/5"
              >
                <div className="px-4 py-3 border-b border-zinc-100">
                  <p className="text-xs font-medium text-zinc-500 truncate">{user.email}</p>
                  <div className="mt-1.5 flex items-center gap-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wide bg-blue-50 text-blue-700 rounded-full px-2 py-0.5">
                      {planBadgeLabel(user)}
                    </span>
                    {creditsLabel && (
                      <span className="text-[10px] font-medium text-zinc-500">
                        {creditsLabel}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={signOut}
                  className="w-full text-left px-4 py-3 text-sm text-zinc-700 hover:bg-zinc-50 transition-colors flex items-center gap-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-zinc-400">
                    <path fillRule="evenodd" d="M3 4.25A2.25 2.25 0 0 1 5.25 2h5.5A2.25 2.25 0 0 1 13 4.25v2a.75.75 0 0 1-1.5 0v-2a.75.75 0 0 0-.75-.75h-5.5a.75.75 0 0 0-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 0 0 .75-.75v-2a.75.75 0 0 1 1.5 0v2A2.25 2.25 0 0 1 10.75 18h-5.5A2.25 2.25 0 0 1 3 15.75V4.25Z" clipRule="evenodd" />
                    <path fillRule="evenodd" d="M19 10a.75.75 0 0 0-.75-.75H8.704l1.048-1.007a.75.75 0 1 0-1.004-1.114l-2.5 2.25a.75.75 0 0 0 0 1.114l2.5 2.25a.75.75 0 1 0 1.004-1.114L8.704 10.75H18.25A.75.75 0 0 0 19 10Z" clipRule="evenodd" />
                  </svg>
                  {t('header.sign_out')}
                </button>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    );
  }

  const signInButtonClass =
    isSidebar
      ? `w-full text-sm font-semibold rounded-xl px-4 py-2.5 transition-colors locale-nowrap ${
          variant === 'dark'
            ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm shadow-blue-900/30'
            : 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm shadow-blue-900/20'
        }`
      : 'text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded-full px-4 py-2 transition-colors shadow-sm shadow-blue-900/20';

  const registerButtonClass =
    `w-full text-sm font-semibold rounded-xl px-4 py-2.5 transition-colors locale-nowrap ${
      variant === 'dark'
        ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm shadow-blue-900/30'
        : 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm shadow-blue-900/20'
    }`;

  const loginButtonClass =
    `w-full text-sm font-medium rounded-xl px-4 py-2.5 transition-colors locale-nowrap ${
      variant === 'dark'
        ? 'text-zinc-200 hover:bg-white/10 border border-white/20'
        : 'text-zinc-700 hover:bg-zinc-100 border border-zinc-200'
    }`;

  return (
    <>
      {isSidebar ? (
        <div className="flex flex-col gap-2 w-full">
          <motion.button
            whileTap={{ scale: 0.98 }}
            onClick={openModal}
            className={registerButtonClass}
          >
            {t('header.register')}
          </motion.button>
          <motion.button
            whileTap={{ scale: 0.98 }}
            onClick={openModal}
            className={loginButtonClass}
          >
            {t('header.login')}
          </motion.button>
        </div>
      ) : (
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={openModal}
          className={signInButtonClass}
        >
          {t('header.sign_in')}
        </motion.button>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 pt-[max(1rem,env(safe-area-inset-top))] pb-[max(1rem,env(safe-area-inset-bottom))] overflow-y-auto"
          >
            <div
              className="absolute inset-0 bg-black/40 backdrop-blur-sm"
              onClick={closeModal}
              aria-hidden
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.94 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="relative w-full max-w-sm max-h-[min(90dvh,calc(100vh-2rem))] overflow-y-auto bg-white rounded-3xl shadow-2xl ring-1 ring-zinc-900/10"
            >
              {/* Header */}
              <div className="px-6 pt-6 pb-4 border-b border-zinc-100 flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-zinc-900 locale-nowrap">{t('auth.modal.title')}</h2>
                  <p className="text-xs text-zinc-500 mt-0.5 locale-text-balance">{t('auth.modal.subtitle')}</p>
                </div>
                <button onClick={closeModal} className="w-8 h-8 rounded-full bg-zinc-100 hover:bg-zinc-200 flex items-center justify-center transition-colors">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-zinc-500">
                    <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                  </svg>
                </button>
              </div>

              <div className="p-6 flex flex-col gap-3">
                {/* ── Options tab ── */}
                {tab === 'options' && (
                  <>
                    {/* Google */}
                    <button
                      onClick={signInWithGoogle}
                      disabled={signingIn !== null}
                      className="w-full flex items-center justify-center gap-3 bg-white hover:bg-zinc-50 text-zinc-800 font-semibold text-sm rounded-xl px-4 py-3 transition-colors border border-zinc-200 shadow-sm disabled:opacity-60 locale-nowrap"
                    >
                      <svg viewBox="0 0 24 24" className="w-5 h-5 flex-shrink-0">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                      </svg>
                      {signingIn === 'google' ? t('auth.google.loading') : t('auth.google')}
                    </button>

                    {/* Microsoft */}
                    <button
                      onClick={signInWithMicrosoft}
                      disabled={signingIn !== null}
                      className="w-full flex items-center justify-center gap-3 bg-white hover:bg-zinc-50 text-zinc-800 font-semibold text-sm rounded-xl px-4 py-3 transition-colors border border-zinc-200 shadow-sm disabled:opacity-60 locale-nowrap"
                    >
                      <svg viewBox="0 0 24 24" className="w-5 h-5 flex-shrink-0">
                        <path fill="#F25022" d="M1 1h10v10H1z"/>
                        <path fill="#7FBA00" d="M13 1h10v10H13z"/>
                        <path fill="#00A4EF" d="M1 13h10v10H1z"/>
                        <path fill="#FFB900" d="M13 13h10v10H13z"/>
                      </svg>
                      {signingIn === 'microsoft' ? t('auth.microsoft.loading') : t('auth.microsoft')}
                    </button>

                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-px bg-zinc-100" />
                      <span className="text-xs text-zinc-400 font-medium">{t('auth.or')}</span>
                      <div className="flex-1 h-px bg-zinc-100" />
                    </div>

                    {/* Email */}
                    <button
                      onClick={() => setTab('email')}
                      className="w-full flex items-center justify-center gap-2.5 bg-zinc-50 hover:bg-zinc-100 text-zinc-700 text-sm font-medium rounded-xl px-4 py-3 transition-colors border border-zinc-200 locale-nowrap"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-zinc-500">
                        <path d="M3 4a2 2 0 0 0-2 2v1.161l8.441 4.221a1.25 1.25 0 0 0 1.118 0L19 7.162V6a2 2 0 0 0-2-2H3Z"/>
                        <path d="m19 8.839-7.77 3.885a2.75 2.75 0 0 1-2.46 0L1 8.839V14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8.839Z"/>
                      </svg>
                      {t('auth.email')}
                    </button>

                  </>
                )}

                {/* ── Email tab ── */}
                {tab === 'email' && (
                  emailSent ? (
                    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="text-center py-4">
                      <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-3">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-6 h-6 text-green-600">
                          <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd"/>
                        </svg>
                      </div>
                      <p className="text-sm font-semibold text-zinc-800">{t('auth.email.sent.title')}</p>
                      <p className="text-xs text-zinc-500 mt-1">{t('auth.email.sent.desc')} <span className="font-medium">{email}</span></p>
                    </motion.div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && signInWithEmail()}
                        placeholder={t('auth.email.placeholder')}
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-3 py-2.5 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        autoFocus />
                      <button onClick={signInWithEmail} disabled={!email || signingIn !== null}
                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm rounded-xl px-4 py-2.5 transition-colors disabled:opacity-50">
                        {signingIn === 'email' ? t('auth.email.sending') : t('auth.email.send')}
                      </button>
                      <button onClick={() => setTab('options')} className="text-xs text-zinc-400 hover:text-zinc-600 transition-colors text-center py-1">
                        {t('auth.email.back')}
                      </button>
                    </div>
                  )
                )}

                {tab === 'options' && (
                  <p className="text-center text-xs text-zinc-400 mt-1">
                    {t('auth.terms')}{' '}
                    <a href="/privacy" target="_blank" rel="noopener noreferrer" className="underline hover:text-zinc-600 transition-colors">{t('auth.terms.link')}</a>
                  </p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
