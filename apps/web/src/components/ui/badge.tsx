import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide transition-colors locale-nowrap',
  {
    variants: {
      variant: {
        default: 'bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
        secondary: 'bg-zinc-100 text-zinc-600 dark:bg-white/10 dark:text-zinc-300',
        success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
        outline: 'border border-zinc-200 text-zinc-600 dark:border-white/15 dark:text-zinc-300',
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
