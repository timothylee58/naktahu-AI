'use client';

import { useI18n } from '@/lib/i18n';
import { CATEGORIES, type CategoryId } from '@/lib/categories';
import { cn } from '@/lib/utils';

interface CategoryTabsProps {
  active: CategoryId;
  onSelect: (id: CategoryId) => void;
}

export function CategoryTabs({ active, onSelect }: CategoryTabsProps) {
  const { t } = useI18n();
  return (
    <div
      role="group"
      aria-label={t('cat.group')}
      // Negative margin + padding lets the scrolling row bleed to the screen
      // edge on mobile while the first tab still aligns with the content.
      className="-mx-4 flex snap-x snap-proximity gap-1 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:justify-center sm:overflow-visible sm:px-0 [&::-webkit-scrollbar]:hidden"
    >
      {CATEGORIES.map((c) => {
        const isActive = c.id === active;
        return (
          <button
            key={c.id}
            type="button"
            aria-pressed={isActive}
            onClick={() => onSelect(c.id)}
            className={cn(
              'h-11 shrink-0 snap-start rounded-full px-4 text-xs font-bold uppercase tracking-[0.05em] transition-colors sm:h-10',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official',
              isActive
                ? 'bg-[var(--nk-tab-active-bg)] text-nk-heritage-text'
                : 'text-nk-muted-aa hover:text-nk-ink',
            )}
          >
            {t(`cat.${c.id}`)}
          </button>
        );
      })}
    </div>
  );
}
