'use client';

import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Globe, ChevronDown } from 'lucide-react';
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
  /** Inline-layout dropdown anchor. 'right' (default) matches the header
   * usage, where the button sits at the right edge of its row. Pass
   * 'left' when the button instead sits near a container's left edge
   * (e.g. packed into a compact sidebar footer row) — right-anchoring
   * there pushes the dropdown's left edge off-screen. */
  align?: 'left' | 'right';
}

export function LangToggle({ variant = 'dark', layout = 'inline', align = 'right' }: LangToggleProps) {
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
    : align === 'left'
      ? 'absolute left-0 mt-2 w-44'
      : 'absolute right-0 mt-2 w-44';

  const optionHover =
    variant === 'light'
      ? 'hover:bg-zinc-50 text-zinc-700'
      : 'hover:bg-white/5 text-zinc-200';

  const activeClass =
    variant === 'light'
      ? 'text-nk-official-dim font-bold'
      : 'text-nk-official font-bold';

  return (
    <div ref={ref} className={`relative ${isSidebar ? 'w-full' : ''}`}>
      <motion.button
        onClick={() => setOpen((o) => !o)}
        whileTap={{ scale: 0.95 }}
        aria-label="Switch language"
        aria-expanded={open}
        className={`flex items-center gap-1.5 border text-xs font-semibold transition-colors locale-nowrap ${isSidebar ? '' : 'rounded-full px-3 py-1.5'} ${buttonBase}`}
      >
        <Globe size={18} strokeWidth={1.75} className="flex-shrink-0 opacity-70" />
        <span className={isSidebar ? 'flex-1 text-left text-sm' : ''}>{isSidebar ? t('lang.label') : current.label}</span>
        <span className={isSidebar ? 'text-xs opacity-70' : ''}>{isSidebar ? current.label : null}</span>
        <ChevronDown
          size={14}
          strokeWidth={1.75}
          className={`opacity-50 transition-transform duration-200 flex-shrink-0 ${open ? 'rotate-180' : ''}`}
        />
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
