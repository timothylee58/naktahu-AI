import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide transition-colors locale-nowrap',
  {
    variants: {
      variant: {
        default: 'bg-nk-official/10 text-nk-official-dim dark:bg-nk-official/15 dark:text-nk-official',
        secondary: 'bg-zinc-100 text-zinc-600 dark:bg-white/10 dark:text-zinc-300',
        success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
        outline: 'border border-zinc-200 text-zinc-600 dark:border-white/15 dark:text-zinc-300',
        // Crowd-sourced/community content (Warung Watch) — gold, distinct
        // from "default"'s official-blue so the two-accent categorization
        // holds wherever Badge is reused.
        community: 'bg-nk-community/10 text-nk-community-dim dark:bg-nk-community/15 dark:text-nk-community',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
