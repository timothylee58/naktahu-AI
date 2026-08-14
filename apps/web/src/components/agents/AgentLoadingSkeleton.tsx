'use client';

import { cn } from '@/lib/utils';

interface AgentLoadingSkeletonProps {
  message?: string;
  className?: string;
}

export function AgentLoadingSkeleton({ message, className }: AgentLoadingSkeletonProps) {
  return (
    <div className={cn('flex flex-col gap-3 rounded-2xl border border-zinc-200 bg-white p-5', className)}>
      <div className="flex items-center gap-3">
        <div className="h-3 w-3 animate-pulse rounded-full bg-nk-official" />
        <span className="text-sm font-medium text-zinc-600">{message ?? 'Processing…'}</span>
      </div>
      <div className="space-y-2.5">
        <div className="h-3 w-full animate-pulse rounded bg-zinc-100" />
        <div className="h-3 w-4/5 animate-pulse rounded bg-zinc-100" style={{ animationDelay: '150ms' }} />
        <div className="h-3 w-3/5 animate-pulse rounded bg-zinc-100" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  );
}
