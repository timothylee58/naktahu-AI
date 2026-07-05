'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

function AuthErrorBannerInner() {
  const { t } = useI18n();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [visible, setVisible] = useState(false);

  const hasError = searchParams.get('error') === 'auth';
  const reason = searchParams.get('reason') ?? '';

  useEffect(() => {
    if (hasError) setVisible(true);
  }, [hasError]);

  const dismiss = () => {
    setVisible(false);
    router.replace('/', { scroll: false });
  };

  const message =
    reason === 'access_denied'
      ? t('auth.error.access_denied')
      : reason === 'exchange_failed'
        ? t('auth.error.exchange_failed')
        : t('auth.error.generic');

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.25 }}
          role="alert"
          className="mx-6 mt-4 flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5 flex-shrink-0 text-red-400 mt-0.5"
            aria-hidden
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
              clipRule="evenodd"
            />
          </svg>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-red-100">{t('auth.error.title')}</p>
            <p className="text-red-200/80 mt-0.5">{message}</p>
          </div>
          <button
            onClick={dismiss}
            aria-label={t('auth.error.dismiss')}
            className="flex-shrink-0 p-1 rounded-lg hover:bg-red-500/20 text-red-300 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function AuthErrorBanner() {
  return (
    <Suspense>
      <AuthErrorBannerInner />
    </Suspense>
  );
}
