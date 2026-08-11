'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

// A scripted typing-simulation, NOT a live query — no backend call, no SSE.
// Deliberately doesn't fabricate a specific hotline phone number, precise
// "confidence %" figure, or per-agency document counts — this repo has no
// verified-current source for any of those to show honestly (see
// AgencyTrustGrid.tsx's role-description-only labels for the same
// reasoning). The "ministry" labels/domains here mirror real citation
// shape ({ministry, title}) from CitationChip.tsx, but the URLs point at
// each agency's real public domain (hasil.gov.my, kwsp.gov.my,
// ssm.com.my) rather than a synthetic link, since those domains are
// public, stable facts, not runtime-verified per-document URLs the way
// live citations are.
//
// Three tabs (tax/epf/business) rather than one fixed scenario — each is
// a single-domain query+answer+citation so switching tabs demonstrates
// domain coverage, not just one canned example.
const SCENARIOS = [
  {
    key: 'tax',
    queryKey: 'landing.preview.demo_query',
    answerKey: 'landing.preview.demo_answer',
    citation: { ministry: 'LHDN', titleKey: 'landing.preview.citation.lhdn', url: 'https://www.hasil.gov.my' },
  },
  {
    key: 'epf',
    queryKey: 'landing.preview.epf.query',
    answerKey: 'landing.preview.epf.answer',
    citation: { ministry: 'KWSP', titleKey: 'landing.preview.citation.kwsp', url: 'https://www.kwsp.gov.my' },
  },
  {
    key: 'business',
    queryKey: 'landing.preview.business.query',
    answerKey: 'landing.preview.business.answer',
    citation: { ministry: 'SSM', titleKey: 'landing.preview.citation.ssm', url: 'https://www.ssm.com.my' },
  },
] as const;

interface InteractiveAnswerPreviewProps {
  isDark?: boolean;
}

export function InteractiveAnswerPreview({ isDark = true }: InteractiveAnswerPreviewProps) {
  const { t } = useI18n();
  const [activeKey, setActiveKey] = useState<(typeof SCENARIOS)[number]['key']>('tax');
  const scenario = SCENARIOS.find((s) => s.key === activeKey) ?? SCENARIOS[0];
  const answer = t(scenario.answerKey);
  const [visibleChars, setVisibleChars] = useState(0);
  const [started, setStarted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Only auto-start the typing simulation once the card scrolls into
  // view, and only once — replaying it every scroll would be distracting
  // rather than demonstrative. Switching tabs afterward still re-types
  // (handled by the tab-switch effect below), since that's a deliberate
  // user action, not an incidental scroll.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || started) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setStarted(true);
          observer.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [started]);

  // Restart the typing animation from scratch whenever the active
  // scenario changes (tab click) — without this, switching tabs would
  // just snap straight to the new answer's full text since visibleChars
  // already exceeds the new (possibly shorter) answer's length.
  useEffect(() => {
    setVisibleChars(0);
  }, [activeKey]);

  useEffect(() => {
    if (!started || visibleChars >= answer.length) return;
    const timeout = setTimeout(() => setVisibleChars((c) => c + 1), 18);
    return () => clearTimeout(timeout);
  }, [started, visibleChars, answer.length]);

  const isDone = visibleChars >= answer.length;
  const cardClass = isDark
    ? 'bg-white/5 border-white/10'
    : 'bg-white border-zinc-200 shadow-sm';
  const chromeClass = isDark ? 'border-white/10' : 'border-zinc-200';
  const queryClass = isDark ? 'text-zinc-100' : 'text-zinc-900';
  const answerClass = isDark ? 'text-zinc-300' : 'text-zinc-700';
  const linkClass = isDark ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700';
  const tabActiveClass = 'bg-[#2563EB] text-white';
  const tabInactiveClass = isDark
    ? 'bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-zinc-200'
    : 'bg-zinc-100 text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700';

  return (
    <div className="max-w-2xl mx-auto w-full flex flex-col gap-3">
      <div className="flex flex-wrap justify-center gap-2" role="tablist">
        {SCENARIOS.map((s) => (
          <button
            key={s.key}
            type="button"
            role="tab"
            aria-selected={activeKey === s.key}
            onClick={() => setActiveKey(s.key)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors locale-nowrap ${
              activeKey === s.key ? tabActiveClass : tabInactiveClass
            }`}
          >
            {t(`domain.${s.key}`)}
          </button>
        ))}
      </div>

      <motion.div
        ref={containerRef}
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className={`w-full rounded-2xl border overflow-hidden ${cardClass}`}
      >
        <div className={`flex items-center gap-1.5 px-4 py-2.5 border-b ${chromeClass}`}>
          <span className="w-2.5 h-2.5 rounded-full bg-red-400/70" aria-hidden />
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400/70" aria-hidden />
          <span className="w-2.5 h-2.5 rounded-full bg-green-400/70" aria-hidden />
        </div>
        <div className="flex flex-col gap-4 px-5 py-5">
          <p className={`text-sm font-semibold locale-text-balance ${queryClass}`}>
            {t(scenario.queryKey)}
          </p>
          <p className={`text-sm leading-relaxed min-h-[3.5rem] locale-text-balance ${answerClass}`}>
            {answer.slice(0, visibleChars)}
            {!isDone && (
              <span className="inline-block w-1.5 h-4 ml-0.5 -mb-0.5 bg-current animate-pulse" aria-hidden />
            )}
          </p>
          {isDone && (
            <div className="flex flex-wrap gap-2">
              <a
                href={scenario.citation.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 bg-blue-50 border border-blue-200 text-blue-800 rounded-full px-3 py-1 text-xs font-medium no-underline transition-colors hover:bg-blue-100 dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-300 dark:hover:bg-blue-500/20"
              >
                <span className="font-semibold">{scenario.citation.ministry}</span>
                <span className="opacity-70">·</span>
                <span>{t(scenario.citation.titleKey)}</span>
              </a>
            </div>
          )}
        </div>
        <div className={`px-5 py-3 border-t text-center ${chromeClass}`}>
          <Link href="/chat" className={`text-xs font-semibold locale-nowrap ${linkClass}`}>
            {t('landing.preview.cta')} →
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
