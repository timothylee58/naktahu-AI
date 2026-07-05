'use client';

import {
  KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useI18n } from '@/lib/i18n';
import { useVoiceInput } from '@/lib/hooks/useVoiceInput';

interface ChatInputProps {
  onSend: (query: string) => void;
  isStreaming: boolean;
  detectedLanguage?: string;
  /** Externally injected query (e.g. from history sidebar or prompt chips). */
  inject?: string;
}

export function ChatInput({
  onSend,
  isStreaming,
  detectedLanguage,
  inject,
}: ChatInputProps) {
  const { t, locale } = useI18n();
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const voiceLang = locale === 'ms' ? 'ms-MY' : locale === 'zh' ? 'zh-MY' : 'en-MY';
  const { isListening, transcript, error: voiceError, startListening, stopListening, available } =
    useVoiceInput({ language: voiceLang });

  useEffect(() => {
    if (transcript) setValue(transcript);
  }, [transcript]);

  // Inject query from history sidebar or prompt chips
  useEffect(() => {
    if (inject !== undefined && inject !== '') {
      setValue(inject);
      textareaRef.current?.focus();
      autoResize();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inject]);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const lineHeight = parseInt(getComputedStyle(el).lineHeight, 10) || 24;
    const maxHeight = lineHeight * 4 + 16;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, isStreaming, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Ctrl+Enter or Cmd+Enter — send
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSubmit();
        return;
      }
      // Enter without shift — send (existing behaviour)
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
        return;
      }
      // Esc — clear input
      if (e.key === 'Escape') {
        setValue('');
        if (textareaRef.current) textareaRef.current.style.height = 'auto';
      }
    },
    [handleSubmit],
  );

  const langLabel = detectedLanguage
    ? detectedLanguage.toUpperCase().slice(0, 2)
    : t('chat.language_indicator');

  return (
    <div className="flex items-end gap-2 bg-white border border-zinc-200 rounded-2xl px-3 py-2 shadow-sm">
      {/* language indicator */}
      <span className="flex-shrink-0 text-[10px] font-semibold text-zinc-400 bg-zinc-100 rounded-full px-2 py-0.5 mb-1 select-none">
        {langLabel}
      </span>

      {/* textarea */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          autoResize();
        }}
        onKeyDown={handleKeyDown}
        placeholder={t('chat.placeholder')}
        rows={1}
        disabled={isStreaming}
        className="flex-1 resize-none bg-transparent text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none leading-6 py-0.5 max-h-24 overflow-y-auto disabled:opacity-50"
        aria-label={t('chat.placeholder')}
      />

      {/* mic button */}
      {available && (
        <div className="relative flex-shrink-0">
        {voiceError && (
          <span className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] bg-zinc-800 text-white rounded px-2 py-0.5 pointer-events-none">
            {voiceError === 'not-allowed' ? t('chat.mic_denied') : voiceError}
          </span>
        )}
        <button
          type="button"
          onClick={isListening ? stopListening : startListening}
          aria-label={t('chat.mic')}
          className={`p-2 rounded-full transition-colors mb-0.5 ${
            isListening
              ? 'bg-red-100 text-red-600 animate-pulse'
              : voiceError
              ? 'text-red-400 hover:text-red-600 hover:bg-red-50'
              : 'text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100'
          }`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5"
            aria-hidden
          >
            <path d="M7 4a3 3 0 0 1 6 0v6a3 3 0 1 1-6 0V4Z" />
            <path d="M5.5 9.643a.75.75 0 0 0-1.5 0V10c0 3.06 2.29 5.585 5.25 5.954V17.5h-1.5a.75.75 0 0 0 0 1.5h4.5a.75.75 0 0 0 0-1.5h-1.5v-1.546A6.001 6.001 0 0 0 16 10v-.357a.75.75 0 0 0-1.5 0V10a4.5 4.5 0 0 1-9 0v-.357Z" />
          </svg>
        </button>
        </div>
      )}

      {/* send button */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!value.trim() || isStreaming}
        aria-label={t('chat.send')}
        className="flex-shrink-0 p-2 rounded-full bg-blue-600 text-white transition-colors hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed mb-0.5"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="w-5 h-5"
          aria-hidden
        >
          <path d="M3.105 2.288a.75.75 0 0 0-.826.95l1.414 4.926A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95 28.897 28.897 0 0 0 15.293-7.154.75.75 0 0 0 0-1.115A28.897 28.897 0 0 0 3.105 2.288Z" />
        </svg>
      </button>
    </div>
  );
}
