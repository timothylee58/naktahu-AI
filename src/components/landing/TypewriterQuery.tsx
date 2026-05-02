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

interface TypewriterQueryProps {
  locale?: 'ms' | 'en';
}

const CHAR_DELAY = 50;
const DELETE_DELAY = 30;
const PAUSE_AFTER_TYPE = 2000;
const PAUSE_BEFORE_TYPE = 500;

export function TypewriterQuery({ locale = 'ms' }: TypewriterQueryProps) {
  const queries = locale === 'ms' ? QUERIES_MS : QUERIES_EN;
  const [displayText, setDisplayText] = useState('');
  const [queryIdx, setQueryIdx] = useState(0);
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
    <span className="text-zinc-400 text-sm">
      {displayText}
      <span className="inline-block w-0.5 h-[1em] bg-zinc-500 align-text-bottom ml-px animate-blink" />
    </span>
  );
}
