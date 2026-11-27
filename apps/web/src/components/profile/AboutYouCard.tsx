'use client';

import { useEffect, useMemo, useState } from 'react';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ChipSelector } from '@/components/agents/ChipSelector';
import { extendedSectorOptions, businessTypeOptions } from '@/lib/agent-catalogs';
import { MALAYSIA_STATE_IDS } from '@/lib/malaysia-states';
import { resolveStateFromPostcode } from '@/lib/postcode';
import { EMPTY_PROFILE, useUserProfile, type UserProfile } from '@/lib/hooks/useUserProfile';

const EMPLOYMENT_IDS = ['employed', 'self_employed', 'unemployed', 'retired', 'student'] as const;

type Draft = {
  state: string | null;
  postcode: string;
  employment_status: string | null;
  business_type: string | null;
  sector: string | null;
  household_size: string;
  share_bumiputera: boolean;
  is_bumiputera: boolean;
};

function toDraft(p: UserProfile): Draft {
  return {
    state: p.state,
    postcode: p.postcode ?? '',
    employment_status: p.employment_status,
    business_type: p.business_type,
    sector: p.sector,
    household_size: p.household_size === null ? '' : String(p.household_size),
    share_bumiputera: p.is_bumiputera !== null,
    is_bumiputera: p.is_bumiputera ?? false,
  };
}

/** Optional facts the user chooses to share once, so agents can prefill them. */
export function AboutYouCard() {
  const { t } = useI18n();
  const { profile, loading, saving, error, signedIn, save, remove } = useUserProfile();
  const [draft, setDraft] = useState<Draft>(() => toDraft(EMPTY_PROFILE));
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (profile) setDraft(toDraft(profile));
  }, [profile]);

  const sectors = useMemo(() => extendedSectorOptions(t), [t]);
  const businessTypes = useMemo(() => businessTypeOptions(t), [t]);
  const employment = useMemo(
    () => EMPLOYMENT_IDS.map((id) => ({ id, label: t(`agents.welfare-eligibility.employment.${id}`) })),
    [t],
  );
  const states = useMemo(
    () => MALAYSIA_STATE_IDS.map((id) => ({ id, label: t(`agents.welfare-eligibility.state.${id}`) })),
    [t],
  );

  if (!signedIn) return null;

  const postcodeInvalid = draft.postcode !== '' && !/^\d{5}$/.test(draft.postcode);
  const sizeNum = draft.household_size.trim() === '' ? null : Number(draft.household_size);
  const sizeInvalid = sizeNum !== null && (!Number.isInteger(sizeNum) || sizeNum < 1 || sizeNum > 30);
  const set = (patch: Partial<Draft>) => {
    setSaved(false);
    setDraft((d) => ({ ...d, ...patch }));
  };
  // Single-select chips: pressing the active one clears it ("not shared").
  const pickOne = (key: 'state' | 'employment_status' | 'business_type' | 'sector') => (id: string) =>
    set({ [key]: draft[key] === id ? null : id } as Partial<Draft>);

  const onSave = async () => {
    if (postcodeInvalid || sizeInvalid) return;
    const ok = await save({
      state: draft.state,
      postcode: draft.postcode || null,
      employment_status: draft.employment_status,
      business_type: draft.business_type,
      sector: draft.sector,
      household_size: sizeNum,
      is_bumiputera: draft.share_bumiputera ? draft.is_bumiputera : null,
    });
    setSaved(ok);
  };

  const onPostcode = (value: string) => {
    const digits = value.replace(/\D/g, '').slice(0, 5);
    const guessed = digits.length === 5 ? resolveStateFromPostcode(digits) : null;
    // Suggest the state only when none is chosen yet; the user can still change it.
    set({ postcode: digits, ...(guessed && !draft.state ? { state: guessed } : {}) });
  };

  const label = 'text-xs font-semibold text-zinc-500 dark:text-zinc-400';

  return (
    <section
      aria-labelledby="about-you-title"
      className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-4 shadow-sm dark:bg-white/5 dark:border-white/10"
    >
      <div>
        <h2 id="about-you-title" className="text-sm font-semibold">{t('profile.about.title')}</h2>
        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{t('profile.about.desc')}</p>
      </div>

      {loading ? (
        <div className="h-24 rounded-xl animate-pulse bg-zinc-100 dark:bg-white/5" />
      ) : (
        <>
          <div className="flex flex-col gap-1.5">
            <span className={label}>{t('profile.about.postcode')}</span>
            <Input
              inputMode="numeric"
              value={draft.postcode}
              onChange={(e) => onPostcode(e.target.value)}
              placeholder="50000"
              aria-invalid={postcodeInvalid}
              className="max-w-[10rem]"
            />
            {postcodeInvalid && (
              <p className="text-xs text-red-600 dark:text-red-400">{t('profile.about.postcode_invalid')}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <span className={label}>{t('profile.about.state')}</span>
            <ChipSelector options={states} selected={draft.state ? [draft.state] : []} onToggle={pickOne('state')} multiple={false} size="sm" />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className={label}>{t('profile.about.employment')}</span>
            <ChipSelector options={employment} selected={draft.employment_status ? [draft.employment_status] : []} onToggle={pickOne('employment_status')} multiple={false} size="sm" />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className={label}>{t('profile.about.business_type')}</span>
            <ChipSelector options={businessTypes} selected={draft.business_type ? [draft.business_type] : []} onToggle={pickOne('business_type')} multiple={false} size="sm" />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className={label}>{t('profile.about.sector')}</span>
            <ChipSelector options={sectors} selected={draft.sector ? [draft.sector] : []} onToggle={pickOne('sector')} multiple={false} size="sm" />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className={label}>{t('profile.about.household')}</span>
            <Input
              type="number"
              min={1}
              max={30}
              value={draft.household_size}
              onChange={(e) => set({ household_size: e.target.value })}
              aria-invalid={sizeInvalid}
              className="max-w-[10rem]"
            />
            {sizeInvalid && (
              <p className="text-xs text-red-600 dark:text-red-400">{t('profile.about.household_invalid')}</p>
            )}
          </div>

          <fieldset className="flex flex-col gap-2 rounded-xl border border-zinc-200 p-3 dark:border-white/10">
            <legend className="px-1 text-xs font-semibold text-zinc-500 dark:text-zinc-400">
              {t('profile.about.bumi.title')}
            </legend>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('profile.about.bumi.desc')}</p>
            <Button
              type="button"
              variant={draft.share_bumiputera ? 'default' : 'outline'}
              size="sm"
              aria-pressed={draft.share_bumiputera}
              className="self-start"
              onClick={() => set({ share_bumiputera: !draft.share_bumiputera })}
            >
              {draft.share_bumiputera ? t('profile.about.bumi.sharing') : t('profile.about.bumi.share')}
            </Button>
            {draft.share_bumiputera && (
              <div className="flex gap-2">
                {[true, false].map((v) => (
                  <Button
                    key={String(v)}
                    type="button"
                    variant={draft.is_bumiputera === v ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => set({ is_bumiputera: v })}
                  >
                    {v ? t('profile.about.bumi.yes') : t('profile.about.bumi.no')}
                  </Button>
                ))}
              </div>
            )}
          </fieldset>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" onClick={() => void onSave()} disabled={saving || postcodeInvalid || sizeInvalid}>
              {saving ? t('profile.about.saving') : t('profile.about.save')}
            </Button>
            <Button type="button" variant="outline" onClick={() => void remove()} disabled={saving}>
              {t('profile.about.delete')}
            </Button>
            {saved && <span role="status" className="text-xs text-emerald-600 dark:text-emerald-400">{t('profile.about.saved')}</span>}
            {error && <span role="alert" className="text-xs text-red-600 dark:text-red-400">{t('profile.about.error')}</span>}
          </div>
        </>
      )}
    </section>
  );
}
