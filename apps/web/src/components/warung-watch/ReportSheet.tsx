'use client';

import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ChevronDown, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { fill, hintKey, levelKey, STATUSES, TEXT_CLASS, type CrowdStatus } from '@/lib/warung-watch/crowd';
import { StatusMeter } from './StatusMeter';

interface ReportSheetProps {
  open: boolean;
  placeName: string;
  status: CrowdStatus | null;
  onStatus: (status: CrowdStatus) => void;
  priceItem: string;
  priceMyr: string;
  onPriceItem: (value: string) => void;
  onPriceMyr: (value: string) => void;
  priceError: boolean;
  reportError: boolean;
  submitting: boolean;
  onSubmit: () => void;
  onClose: () => void;
  t: (key: string) => string;
}

// Spelled out so Tailwind sees each class; a soft tint of the level colour.
const SELECTED_TILE: Record<CrowdStatus, string> = {
  empty: 'border-nk-quiet bg-[color-mix(in_srgb,var(--nk-quiet)_14%,transparent)]',
  moderate: 'border-nk-moderate bg-[color-mix(in_srgb,var(--nk-moderate)_14%,transparent)]',
  packed: 'border-nk-packed bg-[color-mix(in_srgb,var(--nk-packed)_14%,transparent)]',
};

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function ReportSheet(props: ReportSheetProps) {
  const { open, placeName, status, onStatus, priceItem, priceMyr, onPriceItem, onPriceMyr, priceError, reportError, submitting, onSubmit, onClose, t } = props;
  const reduceMotion = useReducedMotion();
  const panelRef = useRef<HTMLDivElement>(null);
  const [priceOpen, setPriceOpen] = useState(false);
  const showPrice = priceOpen || priceError || priceItem !== '' || priceMyr !== '';

  // Remember the opener, move focus in, and give it back on close so keyboard
  // and screen-reader users land where they were.
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const first = panelRef.current?.querySelector<HTMLElement>('input[type="radio"]');
    first?.focus();
    return () => opener?.focus?.();
  }, [open]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab' || !panelRef.current) return;
    const items = Array.from(panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="report-sheet"
          className="fixed inset-0 z-40 flex items-end justify-center bg-black/60 sm:items-center sm:p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.18 }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onClose();
          }}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="warung-report-title"
            onKeyDown={onKeyDown}
            initial={reduceMotion ? false : { y: 48, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { y: 48, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 380, damping: 36 }}
            className="flex max-h-[92dvh] w-full flex-col overflow-y-auto rounded-t-3xl border border-[var(--nk-border)] bg-nk-card text-nk-ink shadow-2xl sm:max-w-md sm:rounded-2xl"
          >
            <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-[var(--nk-track)] sm:hidden" aria-hidden />
            <div className="flex items-start justify-between gap-3 px-5 pt-4">
              <h2 id="warung-report-title" className="font-display text-lg font-bold leading-snug">
                {fill(t('warung_watch.sheet_title'), { name: placeName })}
              </h2>
              <Button type="button" variant="ghost" size="icon" className="-mr-2 h-11 w-11 shrink-0" onClick={onClose} aria-label={t('warung_watch.close')}>
                <X className="h-5 w-5" aria-hidden />
              </Button>
            </div>

            <div className="flex flex-col gap-4 px-5 pb-2 pt-1">
              <p className="text-sm text-nk-muted-aa">{t('warung_watch.sheet_body')}</p>

              <fieldset>
                <legend className="sr-only">{fill(t('warung_watch.sheet_title'), { name: placeName })}</legend>
                <div className="grid grid-cols-3 gap-2">
                  {STATUSES.map((option) => {
                    const checked = status === option;
                    return (
                      <label
                        key={option}
                        className={cn(
                          'relative flex min-h-[6rem] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 px-1 py-3 text-center transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-nk-official',
                          checked ? SELECTED_TILE[option] : 'border-[var(--nk-border)] hover:border-nk-official/40',
                        )}
                      >
                        <input
                          type="radio"
                          name="crowd-level"
                          value={option}
                          checked={checked}
                          onChange={() => onStatus(option)}
                          className="sr-only"
                        />
                        <StatusMeter status={option} size="lg" />
                        <span className={cn('text-sm font-bold', checked ? TEXT_CLASS[option] : 'text-nk-ink')}>{t(levelKey(option))}</span>
                      </label>
                    );
                  })}
                </div>
                <p className="mt-2 min-h-5 text-sm text-nk-muted-aa" aria-live="polite">
                  {status ? t(hintKey(status)) : ''}
                </p>
              </fieldset>

              <div className="border-t border-[var(--nk-border)] pt-3">
                <button
                  type="button"
                  onClick={() => setPriceOpen((current) => !current)}
                  aria-expanded={showPrice}
                  aria-controls="warung-price-fields"
                  className="-mx-1 flex min-h-11 w-full items-center justify-between rounded-lg px-1 text-sm font-semibold text-nk-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official"
                >
                  {t('warung_watch.price_label')}
                  <ChevronDown className={cn('h-4 w-4 transition-transform', showPrice && 'rotate-180')} aria-hidden />
                </button>
                <div id="warung-price-fields" className={cn('mt-2 grid grid-cols-[1fr_6.5rem] gap-2', !showPrice && 'hidden')}>
                  <div className="flex flex-col gap-1">
                    <label htmlFor="warung-price-item" className="text-xs font-semibold text-nk-muted-aa">{t('warung_watch.price_item_label')}</label>
                    <Input id="warung-price-item" value={priceItem} onChange={(event) => onPriceItem(event.target.value)} placeholder={t('warung_watch.price_item_placeholder')} maxLength={80} className="h-11 text-base sm:text-sm" />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label htmlFor="warung-price-myr" className="text-xs font-semibold text-nk-muted-aa">{t('warung_watch.price_amount_label')}</label>
                    <Input id="warung-price-myr" value={priceMyr} onChange={(event) => onPriceMyr(event.target.value)} inputMode="decimal" placeholder="0.00" aria-invalid={priceError} className="h-11 text-base sm:text-sm" />
                  </div>
                  {priceError && (
                    <p role="alert" className="col-span-2 text-sm text-nk-packed-text">{t('warung_watch.price_incomplete')}</p>
                  )}
                </div>
              </div>
            </div>

            <div className="sticky bottom-0 mt-auto flex flex-col gap-2 border-t border-[var(--nk-border)] bg-nk-card px-5 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3">
              {reportError && (
                <p role="alert" className="text-sm text-nk-packed-text">{t('warung_watch.report_failed')}</p>
              )}
              <Button type="button" size="lg" className="h-12 w-full text-base" disabled={!status || submitting} onClick={onSubmit}>
                {submitting ? t('warung_watch.sending') : reportError ? t('warung_watch.retry') : t('warung_watch.send_report')}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
