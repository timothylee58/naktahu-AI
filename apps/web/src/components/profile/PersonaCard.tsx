'use client';

import { useRouter } from 'next/navigation';
import { useI18n } from '@/lib/i18n';
import { usePersona } from '@/lib/hooks/usePersona';
import { MAX_PERSONAS } from '@/lib/persona';
import { resetTour } from '@/lib/tour';
import { Button } from '@/components/ui/button';
import { PersonaPicker } from './PersonaPicker';

export function PersonaCard() {
  const { t } = useI18n();
  const router = useRouter();
  const { personas, setPersonas, saving, saveError } = usePersona();

  const replayTour = () => {
    resetTour();
    router.push('/chat');
  };

  return (
    <section
      aria-labelledby="persona-title"
      className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10"
    >
      <div>
        <h2 id="persona-title" className="text-sm font-semibold">{t('profile.persona.title')}</h2>
        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{t('profile.persona.desc')}</p>
      </div>

      <PersonaPicker selected={personas} onChange={(next) => void setPersonas(next)} disabled={saving} />

      <div aria-live="polite" className="min-h-4 text-xs">
        {saveError ? (
          <span className="font-medium text-red-600 dark:text-red-400">{t('profile.persona.error')}</span>
        ) : (
          <span className="text-zinc-400 dark:text-zinc-500">
            {saving ? t('profile.persona.saving') : t('profile.persona.limit').replace('{n}', String(MAX_PERSONAS))}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-zinc-100 pt-3 dark:border-white/10">
        <span className="text-xs text-zinc-500 dark:text-zinc-400">{t('profile.persona.replay_desc')}</span>
        <Button type="button" variant="outline" size="sm" onClick={replayTour}>
          {t('profile.persona.replay_tour')}
        </Button>
      </div>
    </section>
  );
}
