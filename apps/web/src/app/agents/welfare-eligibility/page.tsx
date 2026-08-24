'use client';

import { useMemo, useState } from 'react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { useI18n } from '@/lib/i18n';
import { agentTitleKey } from '@/lib/agents';

// This agent's `language` field is the target language for the LLM
// explanation step — deriving it from the active UI locale, same
// precedented pattern used by every other agent page.
function localeToApiLanguage(locale: string): 'bm' | 'en' | 'zh' {
  if (locale === 'ms') return 'bm';
  if (locale === 'zh') return 'zh';
  return 'en';
}

const STATE_IDS = [
  'johor', 'kedah', 'kelantan', 'melaka', 'negeri_sembilan', 'pahang',
  'penang', 'perak', 'perlis', 'sabah', 'sarawak', 'selangor', 'terengganu',
  'kl', 'labuan', 'putrajaya',
];

interface MatchedScheme {
  scheme_name: string;
  category: string;
  scope: string;
  description: string;
  implementing_agency: string;
  source_url: string;
  aggregator_url: string | null;
  match_reasons: string[];
}

function WelfareEligibilityPage() {
  const { t, locale } = useI18n();
  const { start } = useAgentApi();

  const [birthYear, setBirthYear] = useState('');
  const [gender, setGender] = useState<string[]>([]);
  const [state, setState] = useState<string[]>([]);
  const [ethnicGroup, setEthnicGroup] = useState<string[]>([]);
  const [maritalStatus, setMaritalStatus] = useState<string[]>([]);
  const [individualIncome, setIndividualIncome] = useState('');
  const [householdIncome, setHouseholdIncome] = useState('');
  const [depChildren, setDepChildren] = useState('');
  const [depElderly, setDepElderly] = useState('');
  const [depOku, setDepOku] = useState('');
  const [depChronic, setDepChronic] = useState('');
  const [employmentStatus, setEmploymentStatus] = useState<string[]>([]);
  const [educationLevel, setEducationLevel] = useState<string[]>([]);
  const [isOku, setIsOku] = useState<string[]>([]);
  const [housingOwnership, setHousingOwnership] = useState<string[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasRun, setHasRun] = useState(false);
  const [matchedSchemes, setMatchedSchemes] = useState<MatchedScheme[]>([]);
  const [noSchemesLoaded, setNoSchemesLoaded] = useState(false);
  const [summary, setSummary] = useState('');

  const stateOptions: ChipOption[] = useMemo(
    () => STATE_IDS.map((id) => ({ id, label: t(`agents.welfare-eligibility.state.${id}`) })),
    [t],
  );
  const genderOptions: ChipOption[] = useMemo(
    () => [
      { id: 'male', label: t('agents.welfare-eligibility.gender.male') },
      { id: 'female', label: t('agents.welfare-eligibility.gender.female') },
    ],
    [t],
  );
  const ethnicOptions: ChipOption[] = useMemo(
    () =>
      ['malay', 'chinese', 'indian', 'bumiputera_sabah_sarawak', 'other'].map((id) => ({
        id,
        label: t(`agents.welfare-eligibility.ethnic.${id}`),
      })),
    [t],
  );
  const maritalOptions: ChipOption[] = useMemo(
    () =>
      ['single', 'married', 'divorced', 'widowed'].map((id) => ({
        id,
        label: t(`agents.welfare-eligibility.marital.${id}`),
      })),
    [t],
  );
  const employmentOptions: ChipOption[] = useMemo(
    () =>
      ['employed', 'self_employed', 'unemployed', 'retired', 'student'].map((id) => ({
        id,
        label: t(`agents.welfare-eligibility.employment.${id}`),
      })),
    [t],
  );
  const educationOptions: ChipOption[] = useMemo(
    () =>
      ['none', 'primary', 'secondary', 'spm', 'diploma', 'degree', 'postgrad'].map((id) => ({
        id,
        label: t(`agents.welfare-eligibility.education.${id}`),
      })),
    [t],
  );
  const housingOptions: ChipOption[] = useMemo(
    () =>
      ['own', 'rented', 'family_owned', 'no_fixed_housing'].map((id) => ({
        id,
        label: t(`agents.welfare-eligibility.housing.${id}`),
      })),
    [t],
  );
  const yesNoOptions: ChipOption[] = useMemo(
    () => [
      { id: 'yes', label: t('agents.welfare-eligibility.oku.yes') },
      { id: 'no', label: t('agents.welfare-eligibility.oku.no') },
    ],
    [t],
  );

  const single = (arr: string[]) => (arr.length ? arr[0] : undefined);
  // Re-clicking an already-selected chip clears it, rather than being a
  // no-op — every one of these fields except state is optional, and the
  // previous behaviour meant an accidental tap on a single-select field
  // could never be undone except by picking a *different* answer instead
  // of "no answer". Reads the field's own current value at click time
  // (fresh closure per render), not a shared/generic toggler.
  const singleToggle = (selected: string[], setter: (v: string[]) => void) => (id: string) =>
    setter(selected.includes(id) ? [] : [id]);
  const canSubmit = state.length > 0; // state is the only field the backend's scope-matching genuinely needs to run at all; everything else narrows the match, nothing else blocks it

  const run = async () => {
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const res = await start('welfare-eligibility-agent', {
        language: localeToApiLanguage(locale),
        birth_year: birthYear ? Number(birthYear) : undefined,
        gender: single(gender),
        state: single(state),
        ethnic_group: single(ethnicGroup),
        marital_status: single(maritalStatus),
        individual_monthly_income_myr: individualIncome ? Number(individualIncome) : undefined,
        household_monthly_income_myr: householdIncome ? Number(householdIncome) : undefined,
        dependents_children: depChildren ? Number(depChildren) : undefined,
        dependents_elderly: depElderly ? Number(depElderly) : undefined,
        dependents_oku: depOku ? Number(depOku) : undefined,
        dependents_chronic_ill: depChronic ? Number(depChronic) : undefined,
        employment_status: single(employmentStatus),
        education_level: single(educationLevel),
        is_oku: single(isOku) === 'yes' ? true : single(isOku) === 'no' ? false : undefined,
        housing_ownership: single(housingOwnership),
      });
      setMatchedSchemes((res.matched_schemes as MatchedScheme[]) ?? []);
      setNoSchemesLoaded(Boolean(res.no_schemes_loaded));
      setSummary(typeof res.summary === 'string' ? res.summary : '');
      setHasRun(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('agents.error.generic'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <AgentPageHeader title={t(agentTitleKey('welfare-eligibility'))} />
      <div className="max-w-2xl mx-auto p-4 flex flex-col gap-4">
        <p className="text-sm text-zinc-600 leading-relaxed dark:text-zinc-400">
          {t('agents.welfare-eligibility.desc')}
        </p>
        {/* Feature is new and the scheme database is still empty (see
            migration 037's own header comment) — said up front, not
            discovered only after someone fills in 14 fields and gets an
            honest-but-disappointing "nothing loaded yet" result. */}
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
          {t('agents.welfare-eligibility.unverified_note')}
        </p>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
            {error}
          </p>
        )}

        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-5 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              {t('agents.welfare-eligibility.section.demographics')}
            </h2>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">
                {t('agents.welfare-eligibility.field.birth_year')}
              </label>
              <input
                type="number"
                min={1900}
                max={2020}
                placeholder={t('agents.welfare-eligibility.field.birth_year_placeholder')}
                value={birthYear}
                onChange={(e) => setBirthYear(e.target.value)}
                className="w-32 border border-zinc-200 rounded-lg px-3 py-2 text-sm bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-600"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.gender')}</label>
              <ChipSelector options={genderOptions} selected={gender} onToggle={singleToggle(gender, setGender)} multiple={false} size="sm" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">
                {t('agents.welfare-eligibility.field.state')} <span className="text-red-500">*</span>
              </label>
              <ChipSelector options={stateOptions} selected={state} onToggle={singleToggle(state, setState)} multiple={false} size="sm" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.ethnic_group')}</label>
              <ChipSelector options={ethnicOptions} selected={ethnicGroup} onToggle={singleToggle(ethnicGroup, setEthnicGroup)} multiple={false} size="sm" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.marital_status')}</label>
              <ChipSelector options={maritalOptions} selected={maritalStatus} onToggle={singleToggle(maritalStatus, setMaritalStatus)} multiple={false} size="sm" />
            </div>
          </div>

          <div className="border-t border-zinc-100 dark:border-white/10" />

          <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              {t('agents.welfare-eligibility.section.household')}
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.individual_income')}</label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-zinc-400 dark:text-zinc-500">RM</span>
                  <input type="number" min={0} placeholder="0" value={individualIncome} onChange={(e) => setIndividualIncome(e.target.value)} className="w-full border border-zinc-200 rounded-lg pl-9 pr-3 py-2 text-sm bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-600" />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.household_income')}</label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-zinc-400 dark:text-zinc-500">RM</span>
                  <input type="number" min={0} placeholder="0" value={householdIncome} onChange={(e) => setHouseholdIncome(e.target.value)} className="w-full border border-zinc-200 rounded-lg pl-9 pr-3 py-2 text-sm bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-600" />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.dependents_children')}</label>
                <input type="number" min={0} max={30} placeholder="0" value={depChildren} onChange={(e) => setDepChildren(e.target.value)} className="border border-zinc-200 rounded-lg px-3 py-2 text-sm bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-600" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.dependents_elderly')}</label>
                <input type="number" min={0} max={30} placeholder="0" value={depElderly} onChange={(e) => setDepElderly(e.target.value)} className="border border-zinc-200 rounded-lg px-3 py-2 text-sm bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-600" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.dependents_oku')}</label>
                <input type="number" min={0} max={30} placeholder="0" value={depOku} onChange={(e) => setDepOku(e.target.value)} className="border border-zinc-200 rounded-lg px-3 py-2 text-sm bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-600" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.dependents_chronic_ill')}</label>
                <input type="number" min={0} max={30} placeholder="0" value={depChronic} onChange={(e) => setDepChronic(e.target.value)} className="border border-zinc-200 rounded-lg px-3 py-2 text-sm bg-transparent focus:outline-none focus:border-nk-official/40 dark:border-white/10 dark:placeholder:text-zinc-600" />
              </div>
            </div>
          </div>

          <div className="border-t border-zinc-100 dark:border-white/10" />

          <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              {t('agents.welfare-eligibility.section.status')}
            </h2>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.employment_status')}</label>
              <ChipSelector options={employmentOptions} selected={employmentStatus} onToggle={singleToggle(employmentStatus, setEmploymentStatus)} multiple={false} size="sm" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.education_level')}</label>
              <ChipSelector options={educationOptions} selected={educationLevel} onToggle={singleToggle(educationLevel, setEducationLevel)} multiple={false} size="sm" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.is_oku')}</label>
              <ChipSelector options={yesNoOptions} selected={isOku} onToggle={singleToggle(isOku, setIsOku)} multiple={false} size="sm" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{t('agents.welfare-eligibility.field.housing_ownership')}</label>
              <ChipSelector options={housingOptions} selected={housingOwnership} onToggle={singleToggle(housingOwnership, setHousingOwnership)} multiple={false} size="sm" />
            </div>
          </div>

          <button
            type="button"
            disabled={loading || !canSubmit}
            onClick={() => void run()}
            className="self-end px-4 py-2 bg-nk-official hover:bg-nk-official-dim hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-blue-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? t('agents.welfare-eligibility.checking') : t('agents.welfare-eligibility.submit')}
          </button>
          <p className="text-[11px] text-zinc-400 dark:text-zinc-500 self-end text-right">
            {t('agents.welfare-eligibility.privacy_note')}
          </p>
        </section>

        {loading && <AgentLoadingSkeleton message={t('agents.welfare-eligibility.checking')} />}

        {!loading && hasRun && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">{t('agents.welfare-eligibility.results_title')}</h2>
              {!noSchemesLoaded && matchedSchemes.length > 0 && (
                <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                  {t('agents.welfare-eligibility.matched_count').replace('{n}', String(matchedSchemes.length))}
                </span>
              )}
            </div>
            {summary && <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed">{summary}</p>}
            {matchedSchemes.length > 0 && (
              <ul className="flex flex-col gap-3">
                {matchedSchemes.map((s, i) => (
                  <li key={i} className="rounded-xl border border-zinc-200 dark:border-white/10 p-3 flex flex-col gap-1.5">
                    <p className="font-semibold text-sm text-zinc-900 dark:text-white">{s.scheme_name}</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">{s.implementing_agency}</p>
                    <p className="text-sm text-zinc-600 dark:text-zinc-300">{s.description}</p>
                    {s.match_reasons.length > 0 && (
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        <span className="font-semibold">{t('agents.welfare-eligibility.why_qualify')}:</span> {s.match_reasons.join('; ')}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-1">
                      <a href={s.source_url} target="_blank" rel="noreferrer" className="text-xs font-semibold text-nk-official-dim dark:text-nk-official">
                        {t('agents.welfare-eligibility.view_source')} →
                      </a>
                      {s.aggregator_url && (
                        <a href={s.aggregator_url} target="_blank" rel="noreferrer" className="text-xs text-zinc-500 dark:text-zinc-400 hover:underline">
                          {t('agents.welfare-eligibility.view_aggregator')} →
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </>
  );
}

export default WelfareEligibilityPage;
