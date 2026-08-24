'use client';

import { useEffect, useRef, useState } from 'react';

const QUERIES_MS = [
  'Bagaimana cara daftar SSM untuk perniagaan baru?',
  'Cara hantar borang cukai LHDN e-Filing',
  'Syarat pengeluaran KWSP akaun 1',
  'Keperluan kemasukan SPM 2025',
];

const QUERIES_EN = [
  'How do I register a new business with SSM?',
  'How to submit LHDN e-Filing tax return',
  'EPF Account 1 withdrawal conditions',
  'SPM 2025 entry requirements',
];

const QUERIES_ZH = [
  '如何向SSM注册新公司？',
  '如何提交LHDN电子报税表？',
  '公积金账户一提款条件',
  '2025年大马教育文凭报名要求',
];

interface TypewriterQueryProps {
  locale?: 'ms' | 'en' | 'zh';
  isDark?: boolean;
}

const CHAR_DELAY = 50;
const DELETE_DELAY = 30;
const PAUSE_AFTER_TYPE = 2000;
const PAUSE_BEFORE_TYPE = 500;

export function TypewriterQuery({ locale = 'ms', isDark = true }: TypewriterQueryProps) {
  const queries = locale === 'zh' ? QUERIES_ZH : locale === 'ms' ? QUERIES_MS : QUERIES_EN;
  const [displayText, setDisplayText] = useState('');
  const [queryIdx, setQueryIdx] = useState(0);

  // Reset to first query when locale changes
  useEffect(() => {
    setQueryIdx(0);
    setDisplayText('');
  }, [locale]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let charIdx = 0;
    let deleting = false;
    const target = queries[queryIdx];

    function tick() {
      if (!deleting) {
        charIdx++;
        setDisplayText(target.slice(0, charIdx));
        if (charIdx === target.length) {
          deleting = true;
          timerRef.current = setTimeout(tick, PAUSE_AFTER_TYPE);
          return;
        }
        timerRef.current = setTimeout(tick, CHAR_DELAY);
      } else {
        charIdx--;
        setDisplayText(target.slice(0, charIdx));
        if (charIdx === 0) {
          timerRef.current = setTimeout(() => {
            setQueryIdx((i) => (i + 1) % queries.length);
          }, PAUSE_BEFORE_TYPE);
          return;
        }
        timerRef.current = setTimeout(tick, DELETE_DELAY);
      }
    }

    timerRef.current = setTimeout(tick, PAUSE_BEFORE_TYPE);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [queryIdx, queries]);

  return (
    <span className={`text-sm ${isDark ? 'text-zinc-200' : 'text-zinc-500'}`}>
      {displayText}
      <span className={`inline-block w-0.5 h-[1em] align-text-bottom ml-px animate-blink ${isDark ? 'bg-zinc-300' : 'bg-zinc-400'}`} />
    </span>
  );
}
