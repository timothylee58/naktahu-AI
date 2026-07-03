'use client';

import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import type { UILocale } from '@/lib/types';

const OPTIONS: { value: UILocale; label: string; native: string }[] = [
  { value: 'ms', label: 'BM', native: 'Bahasa Malaysia' },
  { value: 'en', label: 'EN', native: 'English' },
  { value: 'zh', label: '中文', native: '中文 (简体)' },
];

interface LangToggleProps {
  /** 'dark' = landing page glass style; 'light' = chat header style */
  variant?: 'dark' | 'light';
  /** sidebar = full-width trigger in left panel */
  layout?: 'inline' | 'sidebar';
}

export function LangToggle({ variant = 'dark', layout = 'inline' }: LangToggleProps) {
  const { locale, setLocale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current = OPTIONS.find((o) => o.value === locale) ?? OPTIONS[0];

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const isSidebar = layout === 'sidebar';

  const buttonBase = isSidebar
    ? variant === 'light'
      ? 'w-full justify-between bg-white hover:bg-zinc-50 border-zinc-200 text-zinc-700 rounded-xl px-4 py-2.5'
      : 'w-full justify-between bg-white/5 hover:bg-white/10 border-white/20 text-zinc-200 rounded-xl px-4 py-2.5'
    : variant === 'light'
      ? 'bg-zinc-100 hover:bg-zinc-200 border-zinc-200 text-zinc-700'
      : 'bg-white/5 hover:bg-white/10 border-white/20 text-zinc-200';

  const dropdownBase =
    variant === 'light'
      ? 'bg-white border-zinc-200 shadow-lg'
      : 'bg-[#141929] border-white/10 shadow-xl';

  const dropdownPosition = isSidebar
    ? 'absolute left-0 right-0 bottom-full mb-2'
    : 'absolute right-0 mt-2 w-44';

  const optionHover =
    variant === 'light'
      ? 'hover:bg-zinc-50 text-zinc-700'
      : 'hover:bg-white/5 text-zinc-200';

  const activeClass =
    variant === 'light'
      ? 'text-blue-600 font-bold'
      : 'text-blue-400 font-bold';

  return (
    <div ref={ref} className={`relative ${isSidebar ? 'w-full' : ''}`}>
      <motion.button
        onClick={() => setOpen((o) => !o)}
        whileTap={{ scale: 0.95 }}
        aria-label="Switch language"
        aria-expanded={open}
        className={`flex items-center gap-1.5 border text-xs font-semibold transition-colors locale-nowrap ${isSidebar ? '' : 'rounded-full px-3 py-1.5'} ${buttonBase}`}
      >
        {/* Globe icon */}
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 opacity-60 flex-shrink-0">
          <path fillRule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm-1.465-9.398-.803.321A3.501 3.501 0 0 0 6.5 12.35V13h-.75a.75.75 0 0 0 0 1.5h1.5a.75.75 0 0 0 .75-.75v-1.288a2 2 0 0 1 1.17-1.814l.803-.321a4.5 4.5 0 0 0 .777-.395c.26-.174.62-.174.88 0 .222.148.46.271.712.366l.803.32a2 2 0 0 1 1.17 1.815v.288a.75.75 0 0 0 1.5 0v-.288a3.5 3.5 0 0 0-2.047-3.177l-.803-.32a3 3 0 0 1-.322-.15 1.8 1.8 0 0 0-1.756 0 3.003 3.003 0 0 1-.322.15l-.802.32ZM10 8.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" clipRule="evenodd" />
        </svg>
        <span className={isSidebar ? 'flex-1 text-left text-sm' : ''}>{isSidebar ? t('lang.label') : current.label}</span>
        <span className={isSidebar ? 'text-xs opacity-70' : ''}>{isSidebar ? current.label : null}</span>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-3 h-3 opacity-50 transition-transform duration-200 flex-shrink-0 ${open ? 'rotate-180' : ''}`}>
          <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
        </svg>
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: isSidebar ? 6 : -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: isSidebar ? 6 : -6, scale: 0.96 }}
            transition={{ duration: 0.14 }}
            className={`rounded-2xl border overflow-hidden z-50 ${dropdownPosition} ${dropdownBase}`}
          >
            {OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => { setLocale(opt.value); setOpen(false); }}
                className={`w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors ${optionHover} ${opt.value === locale ? activeClass : ''}`}
              >
                <span className="locale-nowrap">{opt.native}</span>
                <span className={`text-xs locale-nowrap ${opt.value === locale ? '' : 'opacity-50'}`}>{opt.label}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
