'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Phone } from 'lucide-react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { ChipSelector, type ChipOption } from '@/components/agents/ChipSelector';
import { AgentLoadingSkeleton } from '@/components/agents/AgentLoadingSkeleton';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { useI18n } from '@/lib/i18n';

type BodyArea = 'general' | 'head' | 'chest' | 'abdomen' | 'skin';

// Option catalogs were previously module-level constants with hardcoded
// Bahasa Malaysia labels — every chip (body area, symptom, duration,
// severity) showed Malay text regardless of the UI locale, for a health
// tool where clearly understanding your own symptom back to you matters.
// Built as functions of `t` instead, called from inside the component
// where locale context exists; ids (used for backend payloads and
// REDFLAG_QUESTIONS lookups) are unchanged, only the display `label`
// is now localized.
function bodyAreaOptions(t: (key: string) => string): (ChipOption & { id: BodyArea })[] {
  return [
    { id: 'general', label: t('agents.health-triage.body.general'), icon: '🌡' },
    { id: 'head', label: t('agents.health-triage.body.head'), icon: '🧠' },
    { id: 'chest', label: t('agents.health-triage.body.chest'), icon: '🫁' },
    { id: 'abdomen', label: t('agents.health-triage.body.abdomen'), icon: '🫃' },
    { id: 'skin', label: t('agents.health-triage.body.skin'), icon: '🖐' },
  ];
}

// Same symptom set as before, grouped by body area so the guided flow
// shows a shorter, more relevant chip list per step instead of one flat
// list of 10.
function symptomsByArea(t: (key: string) => string): Record<BodyArea, ChipOption[]> {
  return {
    general: [
      { id: 'demam', label: t('agents.health-triage.symptom.demam'), icon: '🤒' },
      { id: 'batuk', label: t('agents.health-triage.symptom.batuk'), icon: '😷' },
    ],
    head: [
      { id: 'sakit_kepala', label: t('agents.health-triage.symptom.sakit_kepala'), icon: '🤕' },
      { id: 'pening', label: t('agents.health-triage.symptom.pening'), icon: '😵' },
    ],
    chest: [
      { id: 'sesak_nafas', label: t('agents.health-triage.symptom.sesak_nafas'), icon: '💨' },
      { id: 'sakit_dada', label: t('agents.health-triage.symptom.sakit_dada'), icon: '💔' },
    ],
    abdomen: [
      { id: 'sakit_perut', label: t('agents.health-triage.symptom.sakit_perut'), icon: '🤧' },
      { id: 'loya', label: t('agents.health-triage.symptom.loya'), icon: '🤢' },
      { id: 'cirit_birit', label: t('agents.health-triage.symptom.cirit_birit'), icon: '💧' },
    ],
    skin: [{ id: 'ruam', label: t('agents.health-triage.symptom.ruam'), icon: '🔴' }],
  };
}

function durationOptions(t: (key: string) => string): ChipOption[] {
  return [
    { id: 'less_1', label: t('agents.health-triage.duration.less_1') },
    { id: '1_3', label: t('agents.health-triage.duration.1_3') },
    { id: '3_7', label: t('agents.health-triage.duration.3_7') },
    { id: 'more_7', label: t('agents.health-triage.duration.more_7') },
  ];
}

type Severity = 'mild' | 'moderate' | 'severe';

function severityOptions(t: (key: string) => string): (ChipOption & { id: Severity })[] {
  return [
    { id: 'mild', label: t('agents.health-triage.severity.mild'), icon: '🟢' },
    { id: 'moderate', label: t('agents.health-triage.severity.moderate'), icon: '🟡' },
    { id: 'severe', label: t('agents.health-triage.severity.severe'), icon: '🔴' },
  ];
}

// Per-symptom red-flag follow-up, one conditional question each — mirrors
// CVS Health's "more questions appear based on your responses" pattern
// (Mobbin: symptom-intake flow) rather than special-casing only chest pain.
// Each entry maps a symptom id to the i18n key for its follow-up question
// and the i18n keys for the yes/no fragments appended to buildMessage() —
// these were raw hardcoded Malay strings, but buildMessage()'s output is
// both the message actually sent to the backend and the text rendered
// back to the user in the Review step and "Your Symptoms" panel, so it
// needs the same localization as everything else on the page.
const REDFLAG_QUESTIONS: Record<string, { questionKey: string; yesKey: string; noKey: string }> = {
  sakit_dada: {
    questionKey: 'agents.health-triage.redflag_chest',
    yesKey: 'agents.health-triage.redflag.sakit_dada.yes',
    noKey: 'agents.health-triage.redflag.sakit_dada.no',
  },
  sesak_nafas: {
    questionKey: 'agents.health-triage.redflag_breath',
    yesKey: 'agents.health-triage.redflag.sesak_nafas.yes',
    noKey: 'agents.health-triage.redflag.sesak_nafas.no',
  },
  sakit_kepala: {
    questionKey: 'agents.health-triage.redflag_headache',
    yesKey: 'agents.health-triage.redflag.sakit_kepala.yes',
    noKey: 'agents.health-triage.redflag.sakit_kepala.no',
  },
  pening: {
    questionKey: 'agents.health-triage.redflag_dizzy',
    yesKey: 'agents.health-triage.redflag.pening.yes',
    noKey: 'agents.health-triage.redflag.pening.no',
  },
  loya: {
    questionKey: 'agents.health-triage.redflag_vomit',
    yesKey: 'agents.health-triage.redflag.loya.yes',
    noKey: 'agents.health-triage.redflag.loya.no',
  },
  sakit_perut: {
    questionKey: 'agents.health-triage.redflag_abdomen',
    yesKey: 'agents.health-triage.redflag.sakit_perut.yes',
    noKey: 'agents.health-triage.redflag.sakit_perut.no',
  },
  cirit_birit: {
    questionKey: 'agents.health-triage.redflag_diarrhea',
    yesKey: 'agents.health-triage.redflag.cirit_birit.yes',
    noKey: 'agents.health-triage.redflag.cirit_birit.no',
  },
  ruam: {
    questionKey: 'agents.health-triage.redflag_rash',
    yesKey: 'agents.health-triage.redflag.ruam.yes',
    noKey: 'agents.health-triage.redflag.ruam.no',
  },
  demam: {
    questionKey: 'agents.health-triage.redflag_fever',
    yesKey: 'agents.health-triage.redflag.demam.yes',
    noKey: 'agents.health-triage.redflag.demam.no',
  },
  batuk: {
    questionKey: 'agents.health-triage.redflag_cough',
    yesKey: 'agents.health-triage.redflag.batuk.yes',
    noKey: 'agents.health-triage.redflag.batuk.no',
  },
};

type Step = 'body' | 'symptoms' | 'duration' | 'severity' | 'details' | 'review';
const STEP_ORDER: Step[] = ['body', 'symptoms', 'duration', 'severity', 'details', 'review'];

type UrgencyLevel = 'emergency' | 'moderate' | 'mild' | 'unknown';

// This keyword match runs against `output.facility_recommendation`, which
// the backend synthesises in the query's own language (this page's
// `language` field, now locale-derived instead of always 'bm' — see
// localeToApiLanguage below). Before that fix, the field was hardcoded to
// 'bm' so this text was always Malay and the bm-only keyword list always
// matched; fixing the hardcoded language exposed this as a real gap for
// en/zh responses, so it needs the same three-language coverage as the
// rest of the page, not just bm+partial-en.
function getUrgencyLevel(output: Record<string, unknown>): UrgencyLevel {
  const rec = String(output.facility_recommendation ?? '').toLowerCase();
  if (rec.includes('999') || rec.includes('kecemasan') || rec.includes('emergency') || rec.includes('紧急')) {
    return 'emergency';
  }
  if (rec.includes('klinik') || rec.includes('clinic') || rec.includes('hari ini') || rec.includes('today') || rec.includes('诊所') || rec.includes('今天')) {
    return 'moderate';
  }
  if (rec.includes('pantau') || rec.includes('monitor') || rec.includes('rest') || rec.includes('rehat') || rec.includes('观察') || rec.includes('休息')) {
    return 'mild';
  }
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

// This agent's `language` field is the target language for the guided
// intake — deriving it from the active UI locale instead of hardcoding
// 'bm' follows the same precedented pattern used by grant-draft-generator/
// sme-compliance-navigator's `queryLanguage`.
function localeToApiLanguage(locale: string): 'bm' | 'en' | 'zh' {
  if (locale === 'ms') return 'bm';
  if (locale === 'zh') return 'zh';
  return 'en';
}

function HealthTriagePageInner() {
  const { t, locale } = useI18n();
  const { start, post, get } = useAgentApi();
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>('body');
  const [bodyArea, setBodyArea] = useState<BodyArea | null>(null);
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [duration, setDuration] = useState<string[]>([]);
  const [severity, setSeverity] = useState<Severity | null>(null);
  const [redFlagAnswers, setRedFlagAnswers] = useState<Record<string, boolean | null>>({});
  const [extraDetails, setExtraDetails] = useState('');
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  // Only set on resume — the "Your symptoms" panel normally derives its
  // text from the local wizard state (bodyArea/selectedSymptoms/etc. via
  // buildMessage()), but a resumed session has none of that local state
  // populated, only the stored `output`. Confirmed Cursor Bugbot finding:
  // without this, resumed sessions showed a blank/misleading symptoms
  // line despite the real composed message being right there in
  // output.message (HealthTriageState's own `message` field, preserved
  // by _public_output).
  const [resumedMessage, setResumedMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportUrl, setExportUrl] = useState<string | null>(null);

  const bodyAreas = useMemo(() => bodyAreaOptions(t), [t]);
  const symptomGroups = useMemo(() => symptomsByArea(t), [t]);
  const durations = useMemo(() => durationOptions(t), [t]);
  const severities = useMemo(() => severityOptions(t), [t]);
  const symptomOptions = useMemo(() => (bodyArea ? symptomGroups[bodyArea] : []), [bodyArea, symptomGroups]);
  const allSymptomLabels = useMemo(() => Object.values(symptomGroups).flat(), [symptomGroups]);
  // Applicable red-flag questions — one per selected symptom that has an
  // entry in REDFLAG_QUESTIONS, in selection order. A concrete example of
  // the guided flow surfacing questions the old flat chip list never asked.
  const applicableRedFlags = useMemo(
    () => selectedSymptoms.filter((id) => REDFLAG_QUESTIONS[id]),
    [selectedSymptoms],
  );

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
        return severity !== null && applicableRedFlags.every((id) => redFlagAnswers[id] !== null && redFlagAnswers[id] !== undefined);
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
    const dur = durations.find((o) => o.id === duration[0])?.label ?? '';
    const sevLabel = severities.find((o) => o.id === severity)?.label ?? '';
    let msg = symptomLabels;
    if (dur) msg += ` ${t('agents.health-triage.since')} ${dur}`;
    if (sevLabel) msg += `, ${t('agents.health-triage.severity_label')}: ${sevLabel}`;
    for (const id of applicableRedFlags) {
      const answer = redFlagAnswers[id];
      if (answer === null || answer === undefined) continue;
      const flag = REDFLAG_QUESTIONS[id];
      msg += `. ${t(answer ? flag.yesKey : flag.noKey)}`;
    }
    if (extraDetails.trim()) msg += `. ${extraDetails.trim()}`;
    return msg;
  };

  // Resume from History's "?run=<agent_runs.id>" link — fetch the stored
  // run and jump straight to the results view instead of the intake flow.
  // Silently falls back to a fresh intake on any failure (bad/expired
  // link, network error) rather than surfacing an error for what's often
  // just a stale link — this is a convenience restore, not a page the
  // user is blocked without.
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const run = await get(`/api/v1/agent-runs/${runId}`);
        const out = (run.output as Record<string, unknown>) ?? {};
        setOutput(out);
        setSessionId(typeof run.session_id === 'string' ? run.session_id : null);
        setResumedMessage(typeof out.message === 'string' ? out.message : null);
        setStep('review');
      } catch {
        /* stale/invalid run id — stays on the fresh intake flow */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await start('health-triage', { message: buildMessage(), language: localeToApiLanguage(locale) });
      setOutput((res.output as Record<string, unknown>) ?? res);
      setSessionId(typeof res.session_id === 'string' ? res.session_id : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('agents.error.generic'));
    } finally {
      setLoading(false);
    }
  };

  const exportPdf = async () => {
    if (!sessionId) return;
    setExporting(true);
    setError(null);
    try {
      const res = await post(`/api/v1/agents/health-triage/${sessionId}/export`, {});
      setExportUrl(typeof res.signed_url === 'string' ? res.signed_url : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('agents.error.generic'));
    } finally {
      setExporting(false);
    }
  };

  const reset = () => {
    setStep('body');
    setBodyArea(null);
    setSelectedSymptoms([]);
    setDuration([]);
    setSeverity(null);
    setRedFlagAnswers({});
    setExtraDetails('');
    setOutput(null);
    setSessionId(null);
    setResumedMessage(null);
    setExportUrl(null);
    setError(null);
  };

  const facilities = (output?.facilities as Array<Record<string, string>>) ?? [];
  const urgency = output ? getUrgencyLevel(output) : 'unknown';
  const urgencyStyle = URGENCY_STYLES[urgency];

  return (
    <>
      <AgentPageHeader title={t('agents.health-triage.title')} />

      {/* Persistent emergency bar — always visible regardless of flow progress,
          not just a line of small gray text above the form. Sticks directly
          under the shared app header (top-16 ≈ that header's rendered height). */}
      <a
        href="tel:999"
        className="sticky top-16 z-20 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-500 transition-colors px-4 py-2 text-white text-sm font-semibold"
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
                      options={bodyAreas}
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
                    <ChipSelector options={durations} selected={duration} onToggle={(id) => setDuration([id])} multiple={false} size="sm" />
                  </>
                )}

                {step === 'severity' && (
                  <>
                    <h2 className="font-semibold text-sm">{t('agents.health-triage.step_severity')}</h2>
                    <ChipSelector
                      options={severities}
                      selected={severity ? [severity] : []}
                      onToggle={(id) => setSeverity(id as Severity)}
                      multiple={false}
                    />
                    {applicableRedFlags.map((id) => {
                      const flag = REDFLAG_QUESTIONS[id];
                      const answer = redFlagAnswers[id] ?? null;
                      return (
                        <div key={id} className="mt-2 rounded-xl border border-red-200 bg-red-50 p-3 dark:border-red-500/30 dark:bg-red-500/10">
                          <p className="text-sm font-medium text-red-800 dark:text-red-300">{t(flag.questionKey)}</p>
                          <div className="mt-2 flex gap-2">
                            <button
                              type="button"
                              onClick={() => setRedFlagAnswers((prev) => ({ ...prev, [id]: true }))}
                              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${answer === true ? 'bg-red-600 border-red-600 text-white' : 'border-red-300 text-red-700 dark:text-red-300 dark:border-red-500/40'}`}
                            >
                              {t('agents.health-triage.yes')}
                            </button>
                            <button
                              type="button"
                              onClick={() => setRedFlagAnswers((prev) => ({ ...prev, [id]: false }))}
                              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${answer === false ? 'bg-red-600 border-red-600 text-white' : 'border-red-300 text-red-700 dark:text-red-300 dark:border-red-500/40'}`}
                            >
                              {t('agents.health-triage.no')}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </>
                )}

                {step === 'details' && (
                  <>
                    <h2 className="font-semibold text-sm">{t('agents.health-triage.step_details')}</h2>
                    <textarea
                      className="border border-zinc-200 rounded-xl p-3 text-sm bg-transparent transition-colors focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10 dark:placeholder:text-zinc-500"
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
              <p className="text-sm text-zinc-700 dark:text-zinc-300">{resumedMessage ?? buildMessage()}</p>
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
                        className="flex-shrink-0 text-xs font-semibold text-nk-official-dim dark:text-nk-official whitespace-nowrap"
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

            {sessionId && (
              <div className="flex items-center gap-3">
                {exportUrl ? (
                  <a
                    href={exportUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-semibold text-nk-official-dim hover:underline dark:text-nk-official"
                  >
                    {t('agents.health-triage.download')}
                  </a>
                ) : (
                  <button
                    type="button"
                    onClick={() => void exportPdf()}
                    disabled={exporting}
                    className="text-sm font-semibold text-nk-official-dim hover:underline dark:text-nk-official disabled:opacity-40"
                  >
                    {exporting ? t('agents.health-triage.exporting') : t('agents.health-triage.export_pdf')}
                  </button>
                )}
              </div>
            )}

            <button
              type="button"
              onClick={reset}
              className="self-start text-sm text-nk-official-dim hover:underline dark:text-nk-official"
            >
              {t('agents.health-triage.new_check')}
            </button>
          </div>
        )}
      </motion.div>
    </>
  );
}

export default function HealthTriagePage() {
  return (
    <Suspense>
      <HealthTriagePageInner />
    </Suspense>
  );
}
