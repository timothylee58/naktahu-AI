'use client';

import { Briefcase, IdCard, Landmark, Wallet, type LucideIcon } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { CATEGORIES, type CategoryIcon, type CategoryId } from '@/lib/categories';
import { cn } from '@/lib/utils';

const ICONS: Record<CategoryIcon, LucideIcon> = { Wallet, Briefcase, IdCard, Landmark };

interface CategoryTilesProps {
  active: CategoryId;
  onSelect: (id: CategoryId) => void;
}

export function CategoryTiles({ active, onSelect }: CategoryTilesProps) {
  const { t } = useI18n();
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-[repeat(auto-fit,minmax(180px,1fr))] sm:gap-4">
      {CATEGORIES.map((c) => {
        const Icon = ICONS[c.icon];
        const isActive = c.id === active;
        return (
          <button
            key={c.id}
            type="button"
            aria-pressed={isActive}
            onClick={() => onSelect(c.id)}
            className={cn(
              'flex min-h-40 flex-col justify-between rounded-[20px] border bg-nk-card p-4 text-left transition-colors sm:min-h-[200px] sm:rounded-3xl sm:p-6',
              'hover:border-nk-official/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official',
              isActive ? 'border-[1.5px] border-nk-official' : 'border-[var(--nk-border)]',
            )}
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--nk-fill-official)] text-nk-official-text sm:h-12 sm:w-12 sm:rounded-[14px]">
              <Icon aria-hidden className="h-[22px] w-[22px] sm:h-[26px] sm:w-[26px]" strokeWidth={1.8} />
            </span>
            <span className="flex flex-col gap-1.5">
              <span className="font-display text-base font-bold text-nk-ink sm:text-[19px]">{t(`cat.${c.id}`)}</span>
              <span className="font-mono text-[11px] text-nk-muted-aa sm:text-xs">{t(`cat.${c.id}.agencies`)}</span>
              <span className="hidden text-sm text-nk-muted-aa sm:block">{t(`cat.${c.id}.example`)}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
