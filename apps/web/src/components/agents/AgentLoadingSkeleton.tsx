'use client';

import { cn } from '@/lib/utils';
import { useI18n } from '@/lib/i18n';

interface AgentLoadingSkeletonProps {
  message?: string;
  className?: string;
}

export function AgentLoadingSkeleton({ message, className }: AgentLoadingSkeletonProps) {
  const { t } = useI18n();
  return (
    <div className={cn('flex flex-col gap-3 rounded-2xl border border-zinc-200 bg-white p-5 dark:border-white/10 dark:bg-white/5', className)}>
      <div className="flex items-center gap-3">
        <div className="h-3 w-3 animate-pulse rounded-full bg-nk-official" />
        <span className="text-sm font-medium text-zinc-600 dark:text-zinc-300">{message ?? t('agents.processing')}</span>
      </div>
      <div className="space-y-2.5">
        <div className="h-3 w-full animate-pulse rounded bg-zinc-100 dark:bg-white/10" />
        <div className="h-3 w-4/5 animate-pulse rounded bg-zinc-100 dark:bg-white/10" style={{ animationDelay: '150ms' }} />
        <div className="h-3 w-3/5 animate-pulse rounded bg-zinc-100 dark:bg-white/10" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  );
}
