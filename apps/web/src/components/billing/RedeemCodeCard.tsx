'use client';

import { useState, type FormEvent } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

// Owns its own card chrome and heading — the host page used to wrap it in a
// <section> with a second title, which rendered the heading twice (and the
// inner copy collided with the description via a negative margin). The
// *result* of a redeem (refreshed credits / plan grant) is still owned by the
// parent page, reported through the two callbacks below.
type RedeemStatus =
  | { kind: 'idle' }
  | { kind: 'success'; message: string }
  | { kind: 'error'; message: string };

function fmt(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), template);
}

interface RedeemCodeCardProps {
  onCreditsGranted?: () => void;
  onPlanGranted?: () => void;
  className?: string;
}

export function RedeemCodeCard({ onCreditsGranted, onPlanGranted, className }: RedeemCodeCardProps) {
  const { t } = useI18n();
  const { post } = useAgentApi();
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<RedeemStatus>({ kind: 'idle' });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = code.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setStatus({ kind: 'idle' });
    try {
      const res = await post('/api/v1/billing/redeem', { code: trimmed });
      if (res.status === 'credits_granted') {
        setStatus({ kind: 'success', message: fmt(t('profile.redeem.status.credits_granted'), { n: Number(res.credits_amount) }) });
        onCreditsGranted?.();
      } else if (res.status === 'plan_granted') {
        setStatus({
          kind: 'success',
          message: fmt(t('profile.redeem.status.plan_granted'), { plan: String(res.plan_tier), days: Number(res.duration_days) }),
        });
        onPlanGranted?.();
      } else {
        setStatus({ kind: 'error', message: t('profile.redeem.status.error') });
      }
      setCode('');
    } catch (err) {
      const detail = err instanceof Error ? err.message : '';
      const key = `profile.redeem.status.${detail.replace(/\s+/g, '_')}`;
      const resolved = t(key);
      setStatus({ kind: 'error', message: resolved === key ? t('profile.redeem.status.error') : resolved });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      aria-labelledby="redeem-code-title"
      className={cn(
        'bg-white rounded-2xl border border-zinc-200 p-5 shadow-sm dark:bg-white/5 dark:border-white/10',
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-nk-official/10 text-nk-official-dim dark:text-nk-official"
          aria-hidden="true"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
            <path d="M2 6.5A2.5 2.5 0 0 1 4.5 4h11A2.5 2.5 0 0 1 18 6.5v1.1a.4.4 0 0 1-.3.39 2.02 2.02 0 0 0 0 4.02.4.4 0 0 1 .3.39v1.1a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 2 13.5v-1.1a.4.4 0 0 1 .3-.39 2.02 2.02 0 0 0 0-4.02A.4.4 0 0 1 2 7.6V6.5Zm9.5 1a.75.75 0 0 0-1.5 0v.75a.75.75 0 0 0 1.5 0V7.5Zm0 2.75a.75.75 0 0 0-1.5 0v.75a.75.75 0 0 0 1.5 0v-.75Zm0 2.5a.75.75 0 0 0-1.5 0v.75a.75.75 0 0 0 1.5 0v-.75Z" />
          </svg>
        </span>
        <div className="min-w-0">
          <h2 id="redeem-code-title" className="text-sm font-semibold">
            {t('billing.redeem_section_title')}
          </h2>
          <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{t('profile.redeem.desc')}</p>
        </div>
      </div>

      <form onSubmit={(e) => void submit(e)} className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Input
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder={t('profile.redeem.placeholder')}
          aria-label={t('profile.redeem.placeholder')}
          aria-invalid={status.kind === 'error'}
          maxLength={32}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          className="h-11 flex-1 font-mono tracking-widest"
        />
        <Button type="submit" size="lg" disabled={loading || code.trim().length < 4} className="sm:min-w-28">
          {loading ? t('profile.redeem.redeeming') : t('profile.redeem.button')}
        </Button>
      </form>

      <div aria-live="polite" className="min-h-5">
        <AnimatePresence mode="wait">
          {status.kind !== 'idle' && (
            <motion.p
              key={`${status.kind}-${status.message}`}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              className={cn(
                'mt-3 flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium',
                status.kind === 'success'
                  ? 'bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-400'
                  : 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400',
              )}
            >
              <span aria-hidden="true">{status.kind === 'success' ? '✓' : '!'}</span>
              {status.message}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
