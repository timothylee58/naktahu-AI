'use client';

import { cn } from '@/lib/utils';

export interface ChipOption {
  id: string;
  label: string;
  icon?: string;
}

interface ChipSelectorProps {
  options: ChipOption[];
  selected: string[];
  onToggle: (id: string) => void;
  multiple?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

export function ChipSelector({
  options,
  selected,
  onToggle,
  multiple = true,
  size = 'md',
  className,
}: ChipSelectorProps) {
  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {options.map((opt) => {
        const isActive = selected.includes(opt.id);
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => {
              if (!multiple && !isActive) {
                onToggle(opt.id);
              } else {
                onToggle(opt.id);
              }
            }}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border font-medium transition-all duration-200',
              size === 'sm' ? 'px-3 py-1 text-xs' : 'px-4 py-2 text-sm',
              isActive
                ? 'border-nk-official/40 bg-nk-official/10 text-nk-official-dim shadow-sm dark:border-nk-official/40 dark:bg-nk-official/15 dark:text-nk-official'
                : 'border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300 hover:bg-zinc-50 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300 dark:hover:bg-white/10',
            )}
          >
            {opt.icon && <span aria-hidden>{opt.icon}</span>}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
