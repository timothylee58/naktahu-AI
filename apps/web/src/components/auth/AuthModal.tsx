'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle: string;
  children: ReactNode;
}

export function AuthModal({ open, onClose, title, subtitle, children }: AuthModalProps) {
  const [portalReady, setPortalReady] = useState(false);

  useEffect(() => {
    setPortalReady(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prev;
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!portalReady || !open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6"
      style={{
        paddingTop: 'max(1rem, env(safe-area-inset-top))',
        paddingBottom: 'max(1rem, env(safe-area-inset-bottom))',
      }}
    >
      <motion.button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-black/50 backdrop-blur-sm border-0 cursor-default"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        onClick={onClose}
      />

      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title"
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 w-full max-w-sm max-h-[min(90dvh,calc(100vh-2rem))] flex flex-col overflow-hidden bg-white rounded-3xl shadow-2xl ring-1 ring-zinc-900/10"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-zinc-100 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id="auth-modal-title" className="text-base font-bold text-zinc-900 locale-nowrap">
              {title}
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5 locale-text-balance">{subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex-shrink-0 w-8 h-8 rounded-full bg-zinc-100 hover:bg-zinc-200 flex items-center justify-center transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-zinc-500">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-3">{children}</div>
      </motion.div>
    </div>,
    document.body,
  );
}
