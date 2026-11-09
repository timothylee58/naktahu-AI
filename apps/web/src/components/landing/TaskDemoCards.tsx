'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion, useInView, useReducedMotion } from 'framer-motion';
import { ArrowRight, Check, Loader2, Pause, Play, Search } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

// Same vetted query/answer/citation strings the old single preview used.
// Citation targets are the agencies' real official homepages only — the
// demo never shows a document URL it can't stand behind.
const DEMOS = [
  {
    key: 'epf',
    queryKey: 'landing.preview.epf.query',
    answerKey: 'landing.preview.epf.answer',
    agency: 'KWSP',
    citationKey: 'landing.preview.citation.kwsp',
  },
  {
    key: 'business',
    queryKey: 'landing.preview.business.query',
    answerKey: 'landing.preview.business.answer',
    agency: 'SSM',
    citationKey: 'landing.preview.citation.ssm',
  },
  {
    key: 'tax',
    queryKey: 'landing.preview.demo_query',
    answerKey: 'landing.preview.demo_answer',
    agency: 'LHDN',
    citationKey: 'landing.preview.citation.lhdn',
  },
] as const;

type Demo = (typeof DEMOS)[number];

// question → searching → found → answer; the answer holds longest so it can
// actually be read before the loop restarts.
const STEP_MS = [1600, 1500, 1000, 5000] as const;
const LAST_STEP = STEP_MS.length - 1;

export function TaskDemoCards() {
  return (
    <div className="grid gap-8 md:grid-cols-3 md:gap-6">
      {DEMOS.map((demo) => (
        <TaskDemoCard key={demo.key} demo={demo} />
      ))}
    </div>
  );
}

function TaskDemoCard({ demo }: { demo: Demo }) {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.4 });
  // Reduced motion: start paused on the finished answer instead of looping.
  const [paused, setPaused] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (reduceMotion) {
      setPaused(true);
      setStep(LAST_STEP);
    }
  }, [reduceMotion]);

  useEffect(() => {
    if (paused || !inView) return;
    const id = window.setTimeout(() => setStep((s) => (s + 1) % STEP_MS.length), STEP_MS[step]);
    return () => window.clearTimeout(id);
  }, [step, paused, inView]);

  const question = t(demo.queryKey);
  const citation = t(demo.citationKey);
  const description = t('landing.demos.sr')
    .replace('{question}', question)
    .replace('{agency}', demo.agency)
    .replace('{citation}', citation);
  const fade = reduceMotion
    ? {}
    : { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0 }, transition: { duration: 0.25 } };

  return (
    <article className="flex flex-col">
      <div
        ref={ref}
        className="relative flex min-h-[400px] flex-col overflow-hidden rounded-3xl border border-[var(--nk-border)] bg-nk-card p-4 sm:p-5"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_20%_10%,rgba(59,91,255,0.14),transparent),radial-gradient(50%_50%_at_90%_90%,rgba(224,141,91,0.10),transparent)]"
        />
        <span className="relative w-fit rounded-full border border-[var(--nk-border)] bg-[var(--nk-fill-official)] px-3 py-1 text-xs font-semibold text-nk-official-text">
          {t(`domain.${demo.key}`)}
        </span>

        {/* Purely visual — the sr-only description below carries the same story. */}
        <div aria-hidden className="relative mx-auto mb-4 mt-5 flex w-full max-w-[300px] flex-col gap-3 text-left text-sm">
          <div className="ml-auto max-w-[90%] rounded-2xl rounded-br-md bg-nk-official px-3.5 py-2.5 font-medium text-white shadow-sm">
            {question}
          </div>

          <AnimatePresence mode="wait">
            {step >= 1 && step < LAST_STEP && (
              <motion.div
                key="search"
                {...fade}
                className="flex items-center gap-2.5 rounded-xl border border-[var(--nk-border)] bg-black/[0.04] dark:bg-white/5 px-3 py-2.5 text-xs text-nk-ink/80"
              >
                {step === 1 ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-nk-official-text" />
                ) : (
                  <Check className="h-4 w-4 shrink-0 text-emerald-500" />
                )}
                <span className="flex flex-col">
                  <span className="font-semibold text-nk-ink">
                    {step === 1
                      ? t('landing.demos.searching').replace('{agency}', demo.agency)
                      : t('landing.demos.found')}
                  </span>
                  <span className="text-nk-muted-aa">{citation}</span>
                </span>
              </motion.div>
            )}
            {step === LAST_STEP && (
              <motion.div
                key="answer"
                {...fade}
                className="flex flex-col gap-2.5 rounded-2xl rounded-bl-md border border-[var(--nk-border)] bg-black/[0.04] dark:bg-white/5 px-3.5 py-3 leading-relaxed text-nk-ink/90"
              >
                <p>{t(demo.answerKey)}</p>
                <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-[var(--nk-border)] px-2.5 py-1 text-[11px] text-nk-ink/80">
                  <Search className="h-3 w-3" />
                  <span className="font-mono font-semibold">{demo.agency}</span>
                  <span>{citation}</span>
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          aria-pressed={paused}
          aria-label={paused ? t('landing.demos.play') : t('landing.demos.pause')}
          className="relative mt-auto ml-auto flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--nk-fill-official)] text-nk-ink transition-colors hover:bg-nk-official hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official"
        >
          {paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
        </button>
        <p className="sr-only">{description}</p>
      </div>

      <h3 className="mt-4 font-display text-lg font-bold text-nk-ink">{t(`landing.demos.${demo.key}.title`)}</h3>
      <p className="mt-1 text-base leading-relaxed text-nk-ink/80">{t(`landing.demos.${demo.key}.caption`)}</p>
      <Link
        href={`/chat?q=${encodeURIComponent(question)}`}
        className={cn(
          'mt-2 inline-flex w-fit items-center gap-1 text-sm font-semibold text-nk-official-text',
          'underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official rounded',
        )}
      >
        {t('landing.demos.try')}
        <ArrowRight aria-hidden className="h-3.5 w-3.5" />
      </Link>
    </article>
  );
}
