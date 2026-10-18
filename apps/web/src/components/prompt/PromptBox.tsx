'use client';

import { useEffect, useRef, type KeyboardEvent, type RefObject } from 'react';
import { ArrowUp, Loader2, Mic, Square, X } from 'lucide-react';
import { useI18n } from '@/lib/i18n';
import { isComposingEnter } from '@/lib/prompt/promptState';
import { cn } from '@/lib/utils';

interface PromptBoxProps {
  variant: 'hero' | 'dock';
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  placeholder: string;
  /** Badge text, already uppercase ("BM", "EN"). */
  languageBadge: string;
  languageDetected: boolean;
  status: 'idle' | 'submitting' | 'disabled';
  piiWarning: boolean;
  mic: { available: boolean; listening: boolean; onToggle: () => void };
  inputRef?: RefObject<HTMLTextAreaElement | null>;
}

function isMac(): boolean {
  return typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);
}

export function PromptBox({
  variant,
  value,
  onChange,
  onSubmit,
  onClear,
  placeholder,
  languageBadge,
  languageDetected,
  status,
  piiWarning,
  mic,
  inputRef,
}: PromptBoxProps) {
  const { t } = useI18n();
  const localRef = useRef<HTMLTextAreaElement>(null);
  const ref = inputRef ?? localRef;
  const disabled = status === 'disabled';
  const submitting = status === 'submitting';
  const hasText = value.trim().length > 0;
  const hero = variant === 'hero';

  // Auto-grow up to the CSS max-height, so a pasted paragraph is readable
  // while a one-liner stays one line.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [value, ref]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      // Enter also commits a CJK IME candidate; sending then would cut the
      // sentence off mid-word.
      if (isComposingEnter(e)) return;
      e.preventDefault();
      onSubmit();
    } else if (e.key === 'Escape' && value) {
      e.preventDefault();
      onClear();
    }
  };

  const borderClass = piiWarning
    ? 'border-nk-community'
    : hasText
      ? 'border-nk-official'
      : 'border-[var(--nk-box-border)]';

  return (
    <div
      className={cn(
        'flex flex-col rounded-3xl border bg-nk-card shadow-[var(--nk-box-shadow)] transition-colors sm:flex-row sm:items-center sm:gap-3',
        hasText || piiWarning ? 'border-[1.5px]' : 'border',
        hero ? 'p-3 pl-4' : 'p-2.5 pl-3.5',
        'focus-within:border-nk-official',
        borderClass,
        disabled && 'pointer-events-none opacity-65',
      )}
    >
      <textarea
        ref={ref}
        rows={1}
        value={value}
        disabled={disabled || submitting}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-label={t('box.label')}
        enterKeyHint="send"
        className={cn(
          'order-1 max-h-40 min-h-14 w-full flex-1 resize-none bg-transparent py-2 text-base leading-normal text-nk-ink outline-none placeholder:text-nk-muted-aa sm:order-2 sm:min-h-12 sm:py-3 sm:text-[17px]',
          submitting && 'text-nk-muted-aa',
        )}
      />

      <div className="order-2 flex items-center justify-between pt-1 sm:contents">
        <span
          className={cn(
            'rounded-full px-2.5 py-1 text-xs font-semibold sm:order-1',
            languageDetected
              ? 'bg-[var(--nk-badge-detected-bg)] text-nk-official-text-strong'
              : 'bg-[var(--nk-badge-bg)] text-nk-muted-aa',
          )}
        >
          {languageBadge}
        </span>

        <div className="flex items-center gap-1.5 sm:contents">
          {hasText && !submitting && (
            <button
              type="button"
              onClick={onClear}
              aria-label={t('box.clear')}
              className="flex h-11 w-11 items-center justify-center rounded-full text-nk-muted-aa transition-colors hover:text-nk-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official sm:order-4"
            >
              <X aria-hidden className="h-5 w-5" />
            </button>
          )}
          {hero && (
            <kbd className="hidden rounded-md bg-[var(--nk-badge-bg)] px-2 py-[3px] font-mono text-xs font-medium text-nk-muted-aa [@media(hover:hover)]:sm:order-3 [@media(hover:hover)]:sm:inline-block">
              {isMac() ? '⌘K' : 'Ctrl K'}
            </kbd>
          )}
          {mic.available && (
            <button
              type="button"
              onClick={mic.onToggle}
              aria-label={mic.listening ? t('box.mic_stop') : t('box.mic')}
              aria-pressed={mic.listening}
              className={cn(
                'flex h-11 w-11 items-center justify-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official sm:order-5',
                mic.listening ? 'bg-[var(--nk-fill-official)] text-nk-official-text' : 'text-nk-ink hover:bg-[var(--nk-badge-bg)]',
              )}
            >
              {mic.listening ? <Square aria-hidden className="h-4 w-4 fill-current" /> : <Mic aria-hidden className="h-[22px] w-[22px]" strokeWidth={1.8} />}
            </button>
          )}
          <button
            type="button"
            onClick={onSubmit}
            disabled={!hasText || submitting || disabled}
            aria-label={t('box.send')}
            aria-busy={submitting}
            className={cn(
              'flex shrink-0 items-center justify-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official focus-visible:ring-offset-2 sm:order-6',
              hero ? 'h-12 w-12' : 'h-11 w-11',
              hasText || submitting
                ? 'bg-nk-official text-white hover:bg-nk-official-dim'
                : 'bg-[var(--nk-badge-bg)] text-nk-muted-aa',
            )}
          >
            {submitting ? <Loader2 aria-hidden className="h-5 w-5 animate-spin motion-reduce:animate-none" /> : <ArrowUp aria-hidden className="h-5 w-5" strokeWidth={2.2} />}
          </button>
        </div>
      </div>
    </div>
  );
}
