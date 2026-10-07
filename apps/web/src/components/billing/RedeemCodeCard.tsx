'use client';

import { useState } from 'react';
import { useI18n } from '@/lib/i18n';
import { useAgentApi } from '@/lib/hooks/useAgentApi';

// Extracted out of profile/page.tsx so /billing can offer the same redeem
// flow without a second hand-copy of this state machine (the two pages
// used to be identical here — same status strings, same POST call — just
// pasted twice). Ownership of the *result* (the refreshed credits number,
// the refreshed plan grant) stays with the parent page, since each host
// already has its own fetch for that data; this component only reports
// that a redeem succeeded via the two callbacks below.
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
  const [redeemInput, setRedeemInput] = useState('');
  const [redeemLoading, setRedeemLoading] = useState(false);
  const [redeemStatus, setRedeemStatus] = useState<RedeemStatus>({ kind: 'idle' });

  const submitRedeemCode = async () => {
    const code = redeemInput.trim();
    if (!code) return;
    setRedeemLoading(true);
    setRedeemStatus({ kind: 'idle' });
    try {
      const res = await post('/api/v1/billing/redeem', { code });
      if (res.status === 'credits_granted') {
        setRedeemStatus({ kind: 'success', message: fmt(t('profile.redeem.status.credits_granted'), { n: Number(res.credits_amount) }) });
        onCreditsGranted?.();
      } else if (res.status === 'plan_granted') {
        setRedeemStatus({
          kind: 'success',
          message: fmt(t('profile.redeem.status.plan_granted'), { plan: String(res.plan_tier), days: Number(res.duration_days) }),
        });
        onPlanGranted?.();
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

  return (
    <div className={className}>
      <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-500 dark:text-zinc-400">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5 text-nk-official-dim dark:text-nk-official">
          <path d="M8 1a.75.75 0 0 1 .75.75v6.19l2.22-2.22a.75.75 0 1 1 1.06 1.06l-3.5 3.5a.75.75 0 0 1-1.06 0l-3.5-3.5a.75.75 0 1 1 1.06-1.06l2.22 2.22V1.75A.75.75 0 0 1 8 1ZM1.75 11a.75.75 0 0 1 .75.75v.5c0 .414.336.75.75.75h9.5a.75.75 0 0 0 .75-.75v-.5a.75.75 0 0 1 1.5 0v.5A2.25 2.25 0 0 1 12.75 14h-9.5A2.25 2.25 0 0 1 1 11.75v-.5a.75.75 0 0 1 .75-.75Z" />
        </svg>
        {t('profile.codes.redeem_label')}
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400 -mt-2 mb-3">{t('profile.redeem.desc')}</p>
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
          className={`text-xs font-medium mt-2 ${
            redeemStatus.kind === 'success'
              ? 'text-green-600 dark:text-green-400'
              : 'text-red-600 dark:text-red-400'
          }`}
        >
          {redeemStatus.message}
        </p>
      )}
    </div>
  );
}
