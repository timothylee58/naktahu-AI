'use client';

import Link from 'next/link';
import {
  KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useI18n } from '@/lib/i18n';
import { useVoiceInput } from '@/lib/hooks/useVoiceInput';
import { inSeasonalWindow } from '@/lib/seasonal-window';
import {
  contextUsagePercent,
  formatContextUsage,
} from '@/lib/context-window';
import { matchAgentRules, type AgentSuggestion } from '@/lib/agent-suggestions';

// Below this length, a keyword substring match is more likely noise than
// real intent ("tax" alone shouldn't redirect someone mid-sentence) — the
// same reasoning as agent-suggestions.ts's own empty-string guard, just
// applied to a live-typing consumer instead of a submitted query.
const MIN_CHARS_FOR_LIVE_SUGGESTION = 6;

// A small, representative spread for the auto-cycling placeholder — not the
// full 10-query PromptChips set, just enough to signal "ask about anything
// civic" without the placeholder text itself becoming a second suggestion
// system competing with the chips below the input.
const CYCLING_EXAMPLES: Record<'ms' | 'en' | 'zh', string[]> = {
  ms: [
    'Bagaimana cara mendaftar syarikat di SSM?',
    'Bila tarikh tutup permohonan geran ini?',
    'Apa yang perlu dilakukan jika MyKad hilang?',
    'Bagaimana cara mengeluarkan wang KWSP?',
  ],
  en: [
    'How do I register a company with SSM?',
    "When does this grant's window close?",
    'What should I do if I lose my MyKad?',
    'How do I withdraw EPF for a home purchase?',
  ],
  zh: [
    '如何在SSM注册公司？',
    '这项资助的申请截止日期是什么时候？',
    '如果身份证遗失了该怎么办？',
    '如何提取公积金用于购房？',
  ],
};
const CYCLE_INTERVAL_MS = 4200;

interface ChatInputProps {
  onSend: (query: string) => void;
  isStreaming: boolean;
  /** Aborts the in-flight answer. Omit to fall back to a disabled send button. */
  onStop?: () => void;
  detectedLanguage?: string;
  /** Externally injected query (e.g. from history sidebar or prompt chips). */
  inject?: string;
  /** Character count from prior messages in the conversation. */
  conversationChars?: number;
  variant?: 'light' | 'dark';
}

export function ChatInput({
  onSend,
  isStreaming,
  onStop,
  detectedLanguage,
  inject,
  conversationChars = 0,
  variant = 'light',
}: ChatInputProps) {
  const { t, locale } = useI18n();
  const isDark = variant === 'dark';
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [seasonal, setSeasonal] = useState(false);
  useEffect(() => {
    setSeasonal(inSeasonalWindow(new Date()));
  }, []);
  // Guards against a same-tick double-submit (e.g. a duplicate/repeated
  // Enter keydown before `value` state has cleared) — released on the next
  // microtask rather than tied to isStreaming, since sending while a
  // previous answer is still streaming is now a valid queue action.
  const submittingRef = useRef(false);

  const voiceLang = locale === 'ms' ? 'ms-MY' : locale === 'zh' ? 'zh-MY' : 'en-MY';
  const { isListening, transcript, error: voiceError, startListening, stopListening, available } =
    useVoiceInput({ language: voiceLang });

  // Smart auto-routing: surface a matching vertical agent while the user is
  // still typing, rather than only after they submit and get a general-RAG
  // answer. Only the first agent-kind match is shown (not the API
  // suggestion agent-suggestions.ts also returns for some rules) — a
  // multi-card banner above the input would compete with the input itself
  // for attention. Dismissed by slug, not a plain boolean, so a dismissal
  // doesn't also suppress a *different* agent match later in the same typed
  // sentence.
  const liveSuggestion = useMemo<AgentSuggestion | null>(() => {
    const trimmed = value.trim();
    if (trimmed.length < MIN_CHARS_FOR_LIVE_SUGGESTION) return null;
    const match = matchAgentRules(trimmed).find((s): s is AgentSuggestion => s.kind === 'agent');
    return match ?? null;
  }, [value]);
  const [dismissedSlug, setDismissedSlug] = useState<string | null>(null);
  const showSuggestionBanner = liveSuggestion !== null && liveSuggestion.slug !== dismissedSlug && !isStreaming;

  useEffect(() => {
    if (transcript) setValue(transcript);
  }, [transcript]);

  // Auto-cycling placeholder — only while the field is genuinely empty and
  // unfocused, so it never fights with what the user is actually typing or
  // reads as it changed mid-thought.
  const cyclingSet = CYCLING_EXAMPLES[locale as 'ms' | 'en' | 'zh'] ?? CYCLING_EXAMPLES.en;
  const [cycleIndex, setCycleIndex] = useState(0);
  useEffect(() => {
    if (focused || value) return;
    const id = window.setInterval(() => {
      setCycleIndex((i) => (i + 1) % cyclingSet.length);
    }, CYCLE_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [focused, value, cyclingSet.length]);

  // ⌘K / Ctrl+K — jump straight to the input from anywhere on the page,
  // matching the command-palette convention rather than inventing a new one.
  useEffect(() => {
    const onKeyDown = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

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
    if (!trimmed || submittingRef.current) return;
    submittingRef.current = true;
    onSend(trimmed);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    queueMicrotask(() => {
      submittingRef.current = false;
    });
  }, [value, onSend]);

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

  const usedChars = conversationChars + value.length;
  const usagePercent = contextUsagePercent(usedChars);
  const usageLabel = t('chat.context_usage').replace('{used}', formatContextUsage(usedChars));

  const shellClass = isDark
    ? 'bg-white/5 border-white/10'
    : 'bg-white border-zinc-200 shadow-sm';
  const langBadgeClass = isDark
    ? 'text-zinc-400 bg-white/10'
    : 'text-zinc-400 bg-zinc-100';
  const inputClass = isDark
    ? 'text-zinc-100 placeholder-zinc-500'
    : 'text-zinc-800 placeholder-zinc-400';
  const micIdleClass = isDark
    ? 'text-zinc-400 hover:text-zinc-200 hover:bg-white/10'
    : 'text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100';
  const contextTrackClass = isDark ? 'bg-white/10' : 'bg-zinc-100';
  const contextLabelClass = isDark ? 'text-zinc-500' : 'text-zinc-400';

  return (
    <div className="flex flex-col gap-1.5 w-full">
    {showSuggestionBanner && liveSuggestion && (
      <div
        className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs ${
          isDark ? 'border-nk-official/30 bg-nk-official/10 text-nk-official' : 'border-nk-official/30 bg-nk-official/10 text-nk-official-dim'
        }`}
      >
        <span aria-hidden>💡</span>
        <span className="flex-1 locale-text-balance">
          {t('chat.suggestion.intro').replace('{agent}', t(liveSuggestion.titleKey))}
        </span>
        <Link
          href={liveSuggestion.href}
          className="flex-shrink-0 font-semibold underline-offset-2 hover:underline locale-nowrap"
        >
          {t('chat.suggestion.open')} →
        </Link>
        <button
          type="button"
          onClick={() => setDismissedSlug(liveSuggestion.slug)}
          aria-label={t('chat.suggestion.dismiss')}
          className="flex-shrink-0 opacity-60 hover:opacity-100"
        >
          ✕
        </button>
      </div>
    )}
    <div
      className={`chat-input-sweep rounded-2xl ${focused ? 'chat-input-sweep--active' : ''}`}
    >
    <div className={`flex items-end gap-2 border rounded-2xl px-3 py-2 ${shellClass}`}>
      <span className={`flex-shrink-0 text-[10px] font-semibold rounded-full px-2 py-0.5 mb-1 select-none ${langBadgeClass}`}>
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
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={isStreaming ? t('chat.placeholder_queue') : cyclingSet[cycleIndex]}
        rows={1}
        className={`flex-1 resize-none bg-transparent text-sm focus:outline-none leading-6 py-0.5 max-h-24 overflow-y-auto ${inputClass}`}
        aria-label={t('chat.placeholder')}
      />

      {/* keyboard hotkey hint — hidden once the field has content or focus,
          same "don't compete with what's typed" rule as the cycling placeholder */}
      {!focused && !value && (
        <kbd
          className={`hidden sm:inline-flex flex-shrink-0 items-center gap-0.5 text-[10px] font-mono rounded px-1.5 py-0.5 mb-1 select-none ${
            isDark ? 'bg-white/10 text-zinc-400' : 'bg-zinc-100 text-zinc-400'
          }`}
        >
          ⌘K
        </kbd>
      )}

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
              ? 'bg-red-100 text-red-600'
              : voiceError
              ? 'text-red-400 hover:text-red-600 hover:bg-red-50'
              : micIdleClass
          }`}
        >
          {isListening ? (
            // "Suara Merdeka" mode: during the seasonal window, recolor the
            // waveform bars to the four Jalur Gemilang colours instead of
            // the default currentColor — a real, honest visual (this IS
            // the live mic waveform, just recoloured), not a fabricated
            // audio-analysis feature.
            <span className="chat-waveform" aria-hidden>
              {seasonal ? (
                <>
                  <span style={{ backgroundColor: '#b3282d' }} />
                  <span style={{ backgroundColor: '#ffffff', outline: '1px solid currentColor' }} />
                  <span style={{ backgroundColor: '#ffcc00' }} />
                  <span style={{ backgroundColor: '#010066' }} />
                  <span style={{ backgroundColor: '#b3282d' }} />
                </>
              ) : (
                <><span /><span /><span /><span /><span /></>
              )}
            </span>
          ) : (
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
          )}
        </button>
        </div>
      )}

      {/* send / stop button */}
      {isStreaming && onStop ? (
        <button
          type="button"
          onClick={onStop}
          aria-label={t('chat.stop')}
          className="flex-shrink-0 p-2 rounded-full bg-zinc-800 text-white transition-colors hover:bg-zinc-700 mb-0.5"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-5 h-5"
            aria-hidden
          >
            <rect x="5" y="5" width="10" height="10" rx="1.5" />
          </svg>
        </button>
      ) : (
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!value.trim() || isStreaming}
          aria-label={t('chat.send')}
          className="flex-shrink-0 p-2 rounded-full bg-nk-official text-white transition-colors hover:bg-nk-official-dim disabled:opacity-40 disabled:cursor-not-allowed mb-0.5"
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
      )}
    </div>
    </div>

    <div className="flex items-center gap-2 px-1">
      <div
        className={`flex-1 h-1 rounded-full overflow-hidden ${contextTrackClass}`}
        role="progressbar"
        aria-valuenow={Math.round(usagePercent)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={t('chat.context_window')}
      >
        <div
          className={`h-full rounded-full transition-all duration-200 ${
            usagePercent > 85 ? 'bg-amber-500' : 'bg-nk-official'
          }`}
          style={{ width: `${usagePercent}%` }}
        />
      </div>
      <span className={`text-[10px] tabular-nums flex-shrink-0 select-none ${contextLabelClass}`}>
        {usageLabel}
      </span>
    </div>
    </div>
  );
}
