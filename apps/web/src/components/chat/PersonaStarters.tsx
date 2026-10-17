'use client';

import { useI18n } from '@/lib/i18n';
import { usePersona } from '@/lib/hooks/usePersona';
import { personaStarters } from '@/lib/persona';

interface PersonaStartersProps {
  onSelect: (query: string) => void;
  disabled?: boolean;
  variant: 'dark' | 'light';
}

export function PersonaStarters({ onSelect, disabled, variant }: PersonaStartersProps) {
  const { t, locale } = useI18n();
  const { personas } = usePersona();
  const starters = personaStarters(personas);
  if (starters.length === 0) return null;

  const lang = locale === 'zh' ? 'Zh' : locale === 'ms' ? 'Ms' : 'En';
  return (
    <div className="flex flex-col gap-1.5">
      <p className={`text-[11px] font-semibold uppercase tracking-wide ${variant === 'dark' ? 'text-zinc-500' : 'text-zinc-400'}`}>
        {t('chat.persona_starters_label')}
      </p>
      <div className="flex flex-wrap gap-2">
        {starters.map((s) => (
          <button
            key={s.queryEn}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(s[`query${lang}`])}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
              variant === 'dark'
                ? 'border-nk-official/30 bg-nk-official/10 text-zinc-200 hover:bg-nk-official/20'
                : 'border-nk-official/30 bg-nk-official/5 text-zinc-700 hover:bg-nk-official/10'
            }`}
          >
            {s[`label${lang}`]}
          </button>
        ))}
      </div>
    </div>
  );
}
