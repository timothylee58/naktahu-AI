'use client';

import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { inSeasonalWindow } from '@/lib/seasonal-window';

// Merdeka (31 Aug) + Hari Malaysia (16 Sep) — one banner covering both, live
// for a window either side rather than exactly on the two dates. Window
// definition lives in lib/seasonal-window.ts, shared with the landing-page
// hero video so the two seasonal surfaces don't drift apart. Dismissal is
// versioned by year (naktahu_seasonal_2026) so a past dismissal doesn't
// silently suppress next year's banner.
const DISMISS_KEY = `naktahu_seasonal_${new Date().getFullYear()}`;

export function SeasonalBanner() {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!inSeasonalWindow(new Date())) return;
    if (localStorage.getItem(DISMISS_KEY)) return;
    setVisible(true);
  }, []);

  const dismiss = () => {
    setVisible(false);
    localStorage.setItem(DISMISS_KEY, '1');
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="overflow-hidden flex-shrink-0"
        >
          <div className="flex items-center justify-center gap-2 bg-nk-heritage/10 border-b border-nk-heritage/20 px-4 py-2 text-center text-sm text-nk-heritage-dim dark:text-nk-heritage">
            <span aria-hidden>🇲🇾</span>
            <span className="locale-text-balance">{t('banner.merdeka.message')}</span>
            <button
              onClick={dismiss}
              aria-label={t('auth.error.dismiss')}
              className="flex-shrink-0 p-0.5 rounded hover:bg-nk-heritage/20 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
              </svg>
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
