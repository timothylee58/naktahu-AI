import * as React from 'react';

import { cn } from '@/lib/utils';

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => (
  <textarea
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
Textarea.displayName = 'Textarea';

export { Textarea };
