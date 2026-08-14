import * as React from 'react';

import { cn } from '@/lib/utils';

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      'w-full rounded-xl border border-zinc-200 bg-transparent px-3 py-2 text-sm transition-colors',
      'placeholder:text-zinc-400 dark:placeholder:text-zinc-500 dark:border-white/10',
      'focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  />
));
Input.displayName = 'Input';

export { Input };
