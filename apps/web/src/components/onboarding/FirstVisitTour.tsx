'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { usePersona } from '@/lib/hooks/usePersona';
import { hasSeenTour, markTourSeen } from '@/lib/tour';
import { Button } from '@/components/ui/button';
import { PersonaPicker } from '@/components/profile/PersonaPicker';

interface TourStep {
  id: 'welcome' | 'persona' | 'ask' | 'trust' | 'more';
  /** CSS selector of the element to spotlight; null = centred card. */
  target: string | null;
}

const STEPS: TourStep[] = [
  { id: 'welcome', target: null },
  { id: 'persona', target: null },
  { id: 'ask', target: '[data-tour="chat-input"]' },
  { id: 'trust', target: null },
  { id: 'more', target: null },
];

const POPOVER_WIDTH = 360;
const EDGE = 16;
const SPOT_PAD = 8;
// Lets PageLoadingScreen / first paint finish so the tour never opens over a
// spinner.
const OPEN_DELAY_MS = 900;

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

function measure(selector: string | null): Rect | null {
  if (!selector) return null;
  const el = document.querySelector(selector);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (r.width === 0 && r.height === 0) return null;
  return { top: r.top - SPOT_PAD, left: r.left - SPOT_PAD, width: r.width + SPOT_PAD * 2, height: r.height + SPOT_PAD * 2 };
}

export function FirstVisitTour() {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion();
  const { personas, setPersonas, saving } = usePersona();
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const [viewport, setViewport] = useState({ w: 0, h: 0 });
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (hasSeenTour()) return;
    const timer = window.setTimeout(() => setOpen(true), OPEN_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, []);

  const step = STEPS[index];

  const reposition = useCallback(() => {
    setViewport({ w: window.innerWidth, h: window.innerHeight });
    setRect(measure(step.target));
  }, [step.target]);

  useEffect(() => {
    if (!open) return;
    reposition();
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
    };
  }, [open, reposition]);

  useEffect(() => {
    if (open) popoverRef.current?.focus();
  }, [open, index]);

  const finish = useCallback(() => {
    markTourSeen();
    setOpen(false);
  }, []);

  const next = useCallback(() => {
    if (index >= STEPS.length - 1) finish();
    else setIndex((i) => i + 1);
  }, [index, finish]);

  const back = useCallback(() => setIndex((i) => Math.max(0, i - 1)), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') finish();
      else if (e.key === 'ArrowRight') next();
      else if (e.key === 'ArrowLeft') back();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, next, back, finish]);

  if (!open) return null;

  const isLast = index === STEPS.length - 1;
  const width = Math.min(POPOVER_WIDTH, viewport.w - EDGE * 2);
  const duration = reduceMotion ? 0 : 0.25;

  // Anchored steps open above the target when it sits in the lower half of
  // the screen (the chat input does), otherwise below it.
  const anchored = rect !== null;
  const placeAbove = anchored && rect.top > viewport.h / 2;
  const left = anchored ? Math.min(Math.max(rect.left + rect.width / 2 - width / 2, EDGE), viewport.w - width - EDGE) : 0;

  const card = (
    <div
      ref={popoverRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-title"
      className="flex max-h-[85vh] flex-col gap-3 overflow-y-auto rounded-3xl bg-white p-5 text-zinc-900 shadow-2xl outline-none dark:bg-[#1B1F2A] dark:text-white"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1" aria-hidden="true">
            {STEPS.map((s, i) => (
              <span
                key={s.id}
                className={`h-1.5 rounded-full transition-all ${i === index ? 'w-6 bg-nk-official' : 'w-1.5 bg-zinc-200 dark:bg-white/15'}`}
              />
            ))}
          </div>
          <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
            {t('tour.step_of').replace('{n}', String(index + 1)).replace('{total}', String(STEPS.length))}
          </span>
        </div>
        <button type="button" onClick={finish} className="text-xs font-medium text-zinc-500 underline hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-white">
          {t('tour.skip')}
        </button>
      </div>

      <h2 id="tour-title" className="font-display text-lg font-bold">{t(`tour.${step.id}.title`)}</h2>
      <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">{t(`tour.${step.id}.body`)}</p>

      {step.id === 'persona' && (
        <div className="flex flex-col gap-2">
          <PersonaPicker selected={personas} onChange={(n) => void setPersonas(n)} disabled={saving} compact />
          <p className="text-[11px] text-zinc-400 dark:text-zinc-500">{t('tour.persona.hint')}</p>
        </div>
      )}

      {step.id === 'trust' && (
        <ul className="flex flex-col gap-2 rounded-2xl border border-nk-official/20 bg-nk-official/5 p-3 text-sm">
          {(['point1', 'point2'] as const).map((p) => (
            <li key={p} className="flex items-start gap-2">
              <span aria-hidden="true" className="text-nk-official-dim dark:text-nk-official">✓</span>
              {t(`tour.trust.${p}`)}
            </li>
          ))}
        </ul>
      )}

      {step.id === 'more' && (
        <div className="flex flex-wrap gap-2">
          <Link href="/agents" onClick={finish} className="rounded-full border border-zinc-200 px-3 py-1.5 text-xs font-medium hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5">
            {t('tour.more.agents')}
          </Link>
          <Link href="/profile" onClick={finish} className="rounded-full border border-zinc-200 px-3 py-1.5 text-xs font-medium hover:bg-zinc-50 dark:border-white/10 dark:hover:bg-white/5">
            {t('tour.more.profile')}
          </Link>
        </div>
      )}

      <div className="mt-1 flex gap-2">
        {index > 0 && (
          <Button type="button" variant="outline" size="lg" onClick={back}>
            {t('tour.back')}
          </Button>
        )}
        <Button type="button" size="lg" className="flex-1" onClick={next}>
          {isLast ? t('tour.done') : t('tour.next')}
        </Button>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[60]">
      {anchored ? (
        <>
          <motion.div
            aria-hidden="true"
            initial={false}
            animate={{ top: rect.top, left: rect.left, width: rect.width, height: rect.height }}
            transition={{ duration }}
            className="pointer-events-none fixed rounded-2xl shadow-[0_0_0_9999px_rgba(0,0,0,0.6)] ring-2 ring-nk-official"
          />
          <motion.div
            initial={false}
            animate={placeAbove ? { left, bottom: viewport.h - rect.top + EDGE, width } : { left, top: rect.top + rect.height + EDGE, width }}
            transition={{ duration }}
            className="fixed"
          >
            {card}
          </motion.div>
        </>
      ) : (
        <div className="flex h-full items-center justify-center bg-black/60 p-4">
          <motion.div
            key={step.id}
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration }}
            className="w-full max-w-[360px]"
          >
            {card}
          </motion.div>
        </div>
      )}
    </div>
  );
}
