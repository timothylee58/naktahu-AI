'use client';

import { useI18n } from '@/lib/i18n';
import { MAX_PERSONAS, PERSONA_IDS, type PersonaId } from '@/lib/persona';
import { cn } from '@/lib/utils';

interface PersonaPickerProps {
  selected: PersonaId[];
  onChange: (next: PersonaId[]) => void;
  disabled?: boolean;
  compact?: boolean;
}

export function PersonaPicker({ selected, onChange, disabled, compact }: PersonaPickerProps) {
  const { t } = useI18n();
  const atLimit = selected.length >= MAX_PERSONAS;

  const toggle = (id: PersonaId) => {
    if (selected.includes(id)) onChange(selected.filter((p) => p !== id));
    else if (!atLimit) onChange([...selected, id]);
  };

  return (
    <div role="group" aria-label={t('profile.persona.title')} className={cn('grid gap-2', compact ? 'grid-cols-2' : 'grid-cols-1 sm:grid-cols-2')}>
      {PERSONA_IDS.map((id) => {
        const active = selected.includes(id);
        const blocked = !active && atLimit;
        return (
          <button
            key={id}
            type="button"
            aria-pressed={active}
            disabled={disabled || blocked}
            onClick={() => toggle(id)}
            className={cn(
              'flex flex-col gap-0.5 rounded-xl border px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official disabled:cursor-not-allowed disabled:opacity-50',
              active
                ? 'border-nk-official bg-nk-official/10'
                : 'border-zinc-200 hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5',
            )}
          >
            <span className="flex items-center justify-between gap-2 text-sm font-semibold">
              {t(`persona.${id}.name`)}
              {active && <span aria-hidden="true" className="text-nk-official-dim dark:text-nk-official">✓</span>}
            </span>
            {!compact && <span className="text-xs text-zinc-500 dark:text-zinc-400">{t(`persona.${id}.desc`)}</span>}
          </button>
        );
      })}
    </div>
  );
}
