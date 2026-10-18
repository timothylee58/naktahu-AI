'use client';

import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import type { DailyQuota } from '@/lib/hooks/useDailyQuota';
import { cn } from '@/lib/utils';

interface QuotaMeterProps {
  quota: DailyQuota;
  onLogin: () => void;
}

export function QuotaMeter({ quota, onLogin }: QuotaMeterProps) {
  const { t } = useI18n();
  const full = quota.used >= quota.limit;
  const percent = Math.min(100, (quota.used / quota.limit) * 100);

  return (
    <div className="flex w-full max-w-[420px] flex-col gap-1.5 text-left">
      <div
        role="progressbar"
        aria-label={t('quota.label')}
        aria-valuemin={0}
        aria-valuemax={quota.limit}
        aria-valuenow={quota.used}
        className="h-1.5 w-full max-w-[240px] overflow-hidden rounded-full bg-[var(--nk-track)]"
      >
        <motion.div
          initial={false}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.2 }}
          className={cn('h-full rounded-full', full ? 'bg-nk-community' : 'bg-nk-official')}
        />
      </div>
      <p className="text-[13px] text-nk-muted-aa" aria-live="polite">
        {t('quota.used').replace('{used}', String(quota.used)).replace('{limit}', String(quota.limit))}
        {' · '}
        <button
          type="button"
          onClick={onLogin}
          className="font-semibold text-nk-official-text underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official"
        >
          {t('quota.login')}
        </button>
      </p>
    </div>
  );
}
