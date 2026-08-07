'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Phone } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { useI18n } from '@/lib/i18n';

type BodyArea = 'general' | 'head' | 'chest' | 'abdomen' | 'skin';

const BODY_AREA_OPTIONS: (ChipOption & { id: BodyArea })[] = [
  { id: 'general', label: 'Umum', icon: '🌡' },
  { id: 'head', label: 'Kepala', icon: '🧠' },
  { id: 'chest', label: 'Dada', icon: '🫁' },
  { id: 'abdomen', label: 'Perut', icon: '🫃' },
  { id: 'skin', label: 'Kulit', icon: '🖐' },
];

// Same symptom set as before, now grouped by body area so the guided flow
// shows a shorter, more relevant chip list per step instead of one flat
// list of 10.
const SYMPTOMS_BY_AREA: Record<BodyArea, ChipOption[]> = {
  general: [
    { id: 'demam', label: 'Demam', icon: '🤒' },
    { id: 'batuk', label: 'Batuk', icon: '😷' },
  ],
  head: [
    { id: 'sakit_kepala', label: 'Sakit kepala', icon: '🤕' },
    { id: 'pening', label: 'Pening', icon: '😵' },
  ],
  chest: [
    { id: 'sesak_nafas', label: 'Sesak nafas', icon: '💨' },
    { id: 'sakit_dada', label: 'Sakit dada', icon: '💔' },
  ],
  abdomen: [
    { id: 'sakit_perut', label: 'Sakit perut', icon: '🤧' },
    { id: 'loya', label: 'Loya / Muntah', icon: '🤢' },
    { id: 'cirit_birit', label: 'Cirit-birit', icon: '💧' },
  ],
  skin: [{ id: 'ruam', label: 'Ruam kulit', icon: '🔴' }],
};

const DURATION_OPTIONS: ChipOption[] = [
  { id: 'less_1', label: '< 1 hari' },
  { id: '1_3', label: '1–3 hari' },
  { id: '3_7', label: '3–7 hari' },
  { id: 'more_7', label: '> 1 minggu' },
];

type Severity = 'mild' | 'moderate' | 'severe';

const SEVERITY_OPTIONS: (ChipOption & { id: Severity })[] = [
  { id: 'mild', label: 'Ringan', icon: '🟢' },
  { id: 'moderate', label: 'Sederhana', icon: '🟡' },
  { id: 'severe', label: 'Teruk', icon: '🔴' },
];

type Step = 'body' | 'symptoms' | 'duration' | 'severity' | 'details' | 'review';
const STEP_ORDER: Step[] = ['body', 'symptoms', 'duration', 'severity', 'details', 'review'];

type UrgencyLevel = 'emergency' | 'moderate' | 'mild' | 'unknown';

function getUrgencyLevel(output: Record<string, unknown>): UrgencyLevel {
  const rec = String(output.facility_recommendation ?? '').toLowerCase();
  if (rec.includes('999') || rec.includes('kecemasan') || rec.includes('emergency')) return 'emergency';
  if (rec.includes('klinik') || rec.includes('today') || rec.includes('hari ini')) return 'moderate';
  if (rec.includes('pantau') || rec.includes('monitor') || rec.includes('rest')) return 'mild';
  return 'moderate';
}

const URGENCY_STYLES: Record<UrgencyLevel, { bg: string; border: string; icon: string; textColor: string }> = {
  emergency: { bg: 'bg-red-50 dark:bg-red-500/10', border: 'border-red-300 dark:border-red-500/40', icon: '🔴', textColor: 'text-red-800 dark:text-red-300' },
  moderate: { bg: 'bg-amber-50 dark:bg-amber-500/10', border: 'border-amber-300 dark:border-amber-500/40', icon: '🟡', textColor: 'text-amber-800 dark:text-amber-300' },
  mild: { bg: 'bg-green-50 dark:bg-green-500/10', border: 'border-green-300 dark:border-green-500/40', icon: '🟢', textColor: 'text-green-800 dark:text-green-300' },
  unknown: { bg: 'bg-zinc-50 dark:bg-white/5', border: 'border-zinc-300 dark:border-white/10', icon: '⚪', textColor: 'text-zinc-800 dark:text-zinc-300' },
};

function directionsUrl(facilityName: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(facilityName)}`;
}

export default function HealthTriagePage() {
  const { t } = useI18n();
  const { start } = useAgentApi();
  const [step, setStep] = useState<Step>('body');
  const [bodyArea, setBodyArea] = useState<BodyArea | null>(null);
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [duration, setDuration] = useState<string[]>([]);
  const [severity, setSeverity] = useState<Severity | null>(null);
  const [chestRadiating, setChestRadiating] = useState<boolean | null>(null);
  const [extraDetails, setExtraDetails] = useState('');
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const symptomOptions = useMemo(() => (bodyArea ? SYMPTOMS_BY_AREA[bodyArea] : []), [bodyArea]);
  const allSymptomLabels = useMemo(
    () => Object.values(SYMPTOMS_BY_AREA).flat(),
    [],
  );
  // The red-flag follow-up (chest pain radiating to arm/jaw) only applies
  // when sakit_dada is among the selected symptoms — a concrete example of
  // the guided flow surfacing a question the old flat chip list never asked.
  const hasChestPainFlag = selectedSymptoms.includes('sakit_dada');

  const toggleSymptom = (id: string) => {
    setSelectedSymptoms((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  };

  const stepIndex = STEP_ORDER.indexOf(step);
  const totalSteps = STEP_ORDER.length;

  const goNext = () => {
    const idx = STEP_ORDER.indexOf(step);
    if (idx < STEP_ORDER.length - 1) setStep(STEP_ORDER[idx + 1]);
  };
  const goBack = () => {
    const idx = STEP_ORDER.indexOf(step);
    if (idx > 0) setStep(STEP_ORDER[idx - 1]);
  };

  const canProceed = (): boolean => {
    switch (step) {
      case 'body':
        return bodyArea !== null;
      case 'symptoms':
        return selectedSymptoms.length > 0;
      case 'duration':
        return duration.length > 0;
      case 'severity':
        return severity !== null && (!hasChestPainFlag || chestRadiating !== null);
      case 'details':
        return true;
      default:
        return true;
    }
  };

  const buildMessage = (): string => {
    const symptomLabels = selectedSymptoms
      .map((id) => allSymptomLabels.find((o) => o.id === id)?.label ?? id)
      .join(', ');
    const dur = DURATION_OPTIONS.find((o) => o.id === duration[0])?.label ?? '';
    const sevLabel = SEVERITY_OPTIONS.find((o) => o.id === severity)?.label ?? '';
    let msg = symptomLabels;
    if (dur) msg += ` sejak ${dur}`;
    if (sevLabel) msg += `, tahap keterukan: ${sevLabel}`;
    if (hasChestPainFlag && chestRadiating !== null) {
      msg += chestRadiating
        ? '. Sakit dada merebak ke lengan/rahang.'
        : '. Sakit dada tidak merebak ke lengan/rahang.';
    }
    if (extraDetails.trim()) msg += `. ${extraDetails.trim()}`;
    return msg;
  };

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await start('health-triage', { message: buildMessage(), language: 'bm' });
      setOutput((res.output as Record<string, unknown>) ?? res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ralat berlaku');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setStep('body');
    setBodyArea(null);
    setSelectedSymptoms([]);
    setDuration([]);
    setSeverity(null);
    setChestRadiating(null);
    setExtraDetails('');
    setOutput(null);
    setError(null);
  };

  const facilities = (output?.facilities as Array<Record<string, string>>) ?? [];
  const urgency = output ? getUrgencyLevel(output) : 'unknown';
  const urgencyStyle = URGENCY_STYLES[urgency];

  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-zinc-50 text-zinc-900 dark:bg-[#0A0F1E] dark:text-white">
      <header className="bg-white/80 backdrop-blur-md supports-[backdrop-filter]:bg-white/70 border-b border-zinc-100 px-4 py-3 flex gap-3 items-center sticky top-0 z-20 dark:bg-[#0A0F1E]/80 dark:border-white/10">
        <Link href="/agents" className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 transition-colors dark:text-blue-400 dark:hover:text-blue-300">
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t('agents.hub.title')}
        </Link>
        <h1 className="font-bold tracking-tight">{t('agents.health-triage.title')}</h1>
      </header>

      {/* Persistent emergency bar — always visible regardless of flow progress,
          not just a line of small gray text above the form. */}
      <a
        href="tel:999"
        className="sticky top-[52px] z-20 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-500 transition-colors px-4 py-2 text-white text-sm font-semibold"
      >
        <Phone className="h-4 w-4" aria-hidden />
        {t('agents.health-triage.emergency_bar')}
      </a>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        <p className="text-xs text-zinc-500 leading-relaxed dark:text-zinc-400">{t('agents.health-triage.disclaimer_intro')}</p>

        {!output && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-5 flex flex-col gap-4 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
            {/* Progress bar */}
            <div className="flex items-center gap-1.5">
              {STEP_ORDER.map((s, i) => (
                <div
                  key={s}
                  className={`h-1.5 flex-1 rounded-full transition-colors ${i <= stepIndex ? 'bg-red-500' : 'bg-zinc-200 dark:bg-white/10'}`}
                />
              ))}
            </div>
            <p className="text-xs text-zinc-400 dark:text-zinc-500">
              {t('agents.health-triage.step_of').replace('{n}', String(stepIndex + 1)).replace('{total}', String(totalSteps))}
            </p>

            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.2 }}
                className="flex flex-col gap-3"
              >
                {step === 'body' && (
                  <>
                    <h2 className="font-semibold text-sm">{t('agents.health-triage.step_body')}</h2>
                    <ChipSelector
                      options={BODY_AREA_OPTIONS}
                      selected={bodyArea ? [bodyArea] : []}
                      onToggle={(id) => {
                        setBodyArea(id as BodyArea);
                        setSelectedSymptoms([]);
                      }}
                      multiple={false}
                    />
                  </>
                )}

                {step === 'symptoms' && (
                  <>
                    <h2 className="font-semibold text-sm">{t('agents.health-triage.step_symptoms')}</h2>
                    <ChipSelector options={symptomOptions} selected={selectedSymptoms} onToggle={toggleSymptom} />
                  </>
                )}

                {step === 'duration' && (
                  <>
                    <h2 className="font-semibold text-sm">{t('agents.health-triage.step_duration')}</h2>
                    <ChipSelector options={DURATION_OPTIONS} selected={duration} onToggle={(id) => setDuration([id])} multiple={false} size="sm" />
                  </>
                )}

                {step === 'severity' && (
                  <>
                    <h2 className="font-semibold text-sm">{t('agents.health-triage.step_severity')}</h2>
                    <ChipSelector
                      options={SEVERITY_OPTIONS}
                      selected={severity ? [severity] : []}
                      onToggle={(id) => setSeverity(id as Severity)}
                      multiple={false}
                    />
                    {hasChestPainFlag && (
                      <div className="mt-2 rounded-xl border border-red-200 bg-red-50 p-3 dark:border-red-500/30 dark:bg-red-500/10">
                        <p className="text-sm font-medium text-red-800 dark:text-red-300">{t('agents.health-triage.redflag_chest')}</p>
                        <div className="mt-2 flex gap-2">
                          <button
                            type="button"
                            onClick={() => setChestRadiating(true)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${chestRadiating === true ? 'bg-red-600 border-red-600 text-white' : 'border-red-300 text-red-700 dark:text-red-300 dark:border-red-500/40'}`}
                          >
                            {t('agents.health-triage.yes')}
                          </button>
                          <button
                            type="button"
                            onClick={() => setChestRadiating(false)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${chestRadiating === false ? 'bg-red-600 border-red-600 text-white' : 'border-red-300 text-red-700 dark:text-red-300 dark:border-red-500/40'}`}
                          >
                            {t('agents.health-triage.no')}
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}

                {step === 'details' && (
                  <>
                    <h2 className="font-semibold text-sm">{t('agents.health-triage.step_details')}</h2>
                    <textarea
                      className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/30 dark:border-white/10 dark:placeholder:text-zinc-500"
                      rows={3}
                      value={extraDetails}
                      onChange={(e) => setExtraDetails(e.target.value)}
                      placeholder={t('agents.health-triage.details_placeholder')}
                    />
                  </>
                )}

                {step === 'review' && (
                  <>
                    <h2 className="font-semibold text-sm">{t('agents.health-triage.step_review')}</h2>
                    <p className="text-sm text-zinc-600 dark:text-zinc-400 bg-zinc-50 dark:bg-white/5 rounded-xl p-3 border border-zinc-100 dark:border-white/10">
                      {buildMessage()}
                    </p>
                  </>
                )}
              </motion.div>
            </AnimatePresence>

            {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}

            <div className="flex items-center justify-between gap-3 pt-1">
              <button
                type="button"
                onClick={goBack}
                disabled={stepIndex === 0 || loading}
                className="px-3 py-2 text-sm text-zinc-500 dark:text-zinc-400 disabled:opacity-0"
              >
                {t('agents.health-triage.back')}
              </button>
              {step === 'review' ? (
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => void submit()}
                  className="px-4 py-2 bg-red-600 hover:bg-red-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-red-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
                >
                  {loading ? t('agents.health-triage.checking') : t('agents.health-triage.get_guidance')}
                </button>
              ) : (
                <button
                  type="button"
                  disabled={!canProceed()}
                  onClick={goNext}
                  className="px-4 py-2 bg-red-600 hover:bg-red-500 transition-colors text-white rounded-xl text-sm font-semibold disabled:opacity-40"
                >
                  {t('agents.health-triage.next')}
                </button>
              )}
            </div>
          </section>
        )}

        {loading && <AgentLoadingSkeleton message={t('agents.health-triage.checking')} />}

        {output && (
          <div className="flex flex-col gap-3">
            {/* Full-width color-coded urgency banner leads the result screen,
                instead of being one plain-weight line inside a generic card. */}
            <section className={`rounded-2xl border-2 p-5 ${urgencyStyle.bg} ${urgencyStyle.border}`}>
              <p className={`text-2xl ${urgencyStyle.textColor}`} aria-hidden>{urgencyStyle.icon}</p>
              <p className={`mt-1 font-bold text-lg ${urgencyStyle.textColor}`}>{String(output.facility_recommendation)}</p>
            </section>

            <section className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-sm dark:bg-white/5 dark:border-white/10">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">
                {t('agents.health-triage.your_symptoms')}
              </h3>
              <p className="text-sm text-zinc-700 dark:text-zinc-300">{buildMessage()}</p>
            </section>

            {facilities.length > 0 && (
              <section className="bg-white border border-zinc-200 rounded-2xl p-4 shadow-sm dark:bg-white/5 dark:border-white/10">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-2">
                  {t('agents.health-triage.nearby_facilities')}
                </h3>
                <ul className="flex flex-col gap-2">
                  {facilities.map((f) => (
                    <li key={f.type} className="flex items-center justify-between gap-3 text-sm border-b border-zinc-100 dark:border-white/10 pb-2 last:border-0 last:pb-0">
                      <div>
                        <p className="font-medium">{f.name}</p>
                        <p className="text-zinc-500 dark:text-zinc-400">{f.action}</p>
                      </div>
                      <a
                        href={directionsUrl(f.name)}
                        target="_blank"
                        rel="noreferrer"
                        className="flex-shrink-0 text-xs font-semibold text-blue-600 dark:text-blue-400 whitespace-nowrap"
                      >
                        {t('agents.health-triage.get_directions')} →
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 p-3 rounded-xl dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30">
              {String(output.disclaimer)}
            </p>

            <button
              type="button"
              onClick={reset}
              className="self-start text-sm text-blue-600 hover:underline dark:text-blue-400"
            >
              {t('agents.health-triage.new_check')}
            </button>
          </div>
        )}
      </motion.div>
    </main>
  );
}
