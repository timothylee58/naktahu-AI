'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';

export function AuthButton() {
  const { t } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [emailMode, setEmailMode] = useState(false);
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user);
      setLoading(false);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
        setEmailMode(false);
        setSent(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const signInWithGoogle = () => {
    supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  };

  const signInWithEmail = async () => {
    if (!email) return;
    await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    setSent(true);
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setOpen(false);
  };

  if (loading) {
    return <div className="w-28 h-8 rounded-full bg-zinc-700 animate-pulse" />;
  }

  if (user) {
    return (
      <div ref={dropdownRef} className="relative">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 rounded-full px-3 py-1.5 hover:bg-white/10 transition-colors"
        >
          {user.user_metadata?.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={user.user_metadata.avatar_url as string}
              alt="avatar"
              className="w-7 h-7 rounded-full border border-white/20"
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
            <motion.div
              initial={{ opacity: 0, y: -6, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.96 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 mt-2 w-48 bg-[#0F1628] border border-white/10 rounded-xl shadow-xl z-50 overflow-hidden"
            >
              <div className="px-4 py-3 border-b border-white/10">
                <p className="text-xs text-zinc-400 truncate">{user.email}</p>
              </div>
              <button
                onClick={signOut}
                className="w-full text-left px-4 py-3 text-sm text-zinc-300 hover:bg-white/5 transition-colors"
              >
                {t('header.sign_out')}
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  return (
    <div ref={dropdownRef} className="relative">
      <motion.button
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.97 }}
        onClick={() => { setOpen((o) => !o); setEmailMode(false); setSent(false); }}
        className="text-sm font-semibold bg-[#2563EB] hover:bg-blue-500 text-white rounded-full px-4 py-2 transition-colors shadow-lg shadow-blue-900/30"
      >
        {t('header.sign_in')}
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.18 }}
            className="absolute right-0 mt-3 w-72 bg-[#0F1628] border border-white/10 rounded-2xl shadow-2xl z-50 overflow-hidden"
          >
            <div className="px-5 py-4 border-b border-white/10">
              <p className="text-sm font-semibold text-white">Welcome to NakTahu</p>
              <p className="text-xs text-zinc-400 mt-0.5">Sign in to save your history</p>
            </div>

            <div className="p-4 flex flex-col gap-3">
              {/* Google OAuth */}
              <button
                onClick={signInWithGoogle}
                className="w-full flex items-center justify-center gap-3 bg-white hover:bg-zinc-100 text-zinc-900 font-semibold text-sm rounded-xl px-4 py-2.5 transition-colors"
              >
                <svg viewBox="0 0 24 24" className="w-4 h-4" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Continue with Google
              </button>

              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-white/10" />
                <span className="text-xs text-zinc-500">or</span>
                <div className="flex-1 h-px bg-white/10" />
              </div>

              {/* Email magic link */}
              {sent ? (
                <div className="text-center py-2">
                  <p className="text-sm text-green-400 font-medium">✓ Check your email</p>
                  <p className="text-xs text-zinc-400 mt-1">Magic link sent to {email}</p>
                </div>
              ) : emailMode ? (
                <div className="flex flex-col gap-2">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && signInWithEmail()}
                    placeholder="you@email.com"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500"
                    autoFocus
                  />
                  <button
                    onClick={signInWithEmail}
                    className="w-full bg-[#2563EB] hover:bg-blue-500 text-white font-semibold text-sm rounded-xl px-4 py-2.5 transition-colors"
                  >
                    Send magic link
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setEmailMode(true)}
                  className="w-full flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 text-zinc-300 text-sm font-medium rounded-xl px-4 py-2.5 transition-colors border border-white/10"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                    <path d="M3 4a2 2 0 0 0-2 2v1.161l8.441 4.221a1.25 1.25 0 0 0 1.118 0L19 7.162V6a2 2 0 0 0-2-2H3Z" />
                    <path d="m19 8.839-7.77 3.885a2.75 2.75 0 0 1-2.46 0L1 8.839V14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8.839Z" />
                  </svg>
                  Continue with Email
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
