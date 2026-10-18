'use client';

import { useEffect, useRef } from 'react';
import { useI18n } from '@/lib/i18n';
import { useVoiceInput } from '@/lib/hooks/useVoiceInput';
import { detectLanguage } from '@/lib/prompt/detectLanguage';
import type { DailyQuota } from '@/lib/hooks/useDailyQuota';
import { Button } from '@/components/ui/button';
import { PiiWarning } from '@/components/prompt/PiiWarning';
import { PromptBox } from '@/components/prompt/PromptBox';
import { QuotaMeter } from '@/components/prompt/QuotaMeter';
import { usePromptBox } from '@/components/prompt/usePromptBox';

interface GuestDockProps {
  onSend: (text: string) => void;
  isStreaming: boolean;
  onStop: () => void;
  /** Language the backend reported for the last answer, e.g. "en". */
  detectedLanguage?: string;
  /** Text pushed in from prompt chips or ?q= (same contract as ChatInput). */
  inject: string;
  quota: DailyQuota | null;
  exhausted: boolean;
  onLogin: () => void;
}

const VOICE_LOCALES = { ms: 'ms-MY', en: 'en-MY', zh: 'zh-MY' } as const;
const BADGES = { ms: 'BM', en: 'EN', zh: '中文' } as const;
type Lang = keyof typeof BADGES;

function asLang(value: string | undefined): Lang | null {
  const v = value?.toLowerCase().slice(0, 2);
  return v === 'ms' || v === 'bm' ? 'ms' : v === 'en' ? 'en' : v === 'zh' ? 'zh' : null;
}

// Guest-only composer. Signed-in users keep ChatInput, which carries the
// queue-while-streaming and agent-suggestion features; guests get the same
// prompt box as the homepage so the handoff feels like one surface.
export function GuestDock({ onSend, isStreaming, onStop, detectedLanguage, inject, quota, exhausted, onLogin }: GuestDockProps) {
  const { t, locale } = useI18n();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const box = usePromptBox({ onSend });
  const { fill } = box;

  useEffect(() => {
    if (inject) {
      fill(inject);
      inputRef.current?.focus();
    }
  }, [inject, fill]);

  const voice = useVoiceInput({ language: VOICE_LOCALES[locale as Lang] ?? 'ms-MY' });
  const { transcript } = voice;
  useEffect(() => {
    if (transcript) fill(transcript);
  }, [transcript, fill]);

  const uiLang: Lang = locale === 'zh' ? 'zh' : locale === 'en' ? 'en' : 'ms';
  const typed = detectLanguage(box.value);
  const lang = typed ?? asLang(detectedLanguage) ?? uiLang;

  return (
    <div className="flex flex-col gap-2">
      <PromptBox
        variant="dock"
        value={box.value}
        onChange={box.type}
        onSubmit={isStreaming ? () => undefined : box.submit}
        onClear={box.clear}
        placeholder={exhausted ? t('quota.exhausted') : t('chat.placeholder')}
        languageBadge={BADGES[lang]}
        languageDetected={lang !== uiLang}
        status={exhausted ? 'disabled' : isStreaming ? 'streaming' : 'idle'}
        onStop={onStop}
        piiWarning={box.piiDetected}
        mic={{
          available: voice.available,
          listening: voice.isListening,
          onToggle: voice.isListening ? voice.stopListening : voice.startListening,
        }}
        inputRef={inputRef}
      />
      {box.piiDetected && <PiiWarning onRemove={box.stripPii} />}

      {exhausted ? (
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" onClick={onLogin}>
            {t('header.login')}
          </Button>
          <button type="button" onClick={onLogin} className="text-sm font-semibold text-nk-official-text underline underline-offset-2">
            {t('quota.register')}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          {quota ? <QuotaMeter quota={quota} onLogin={onLogin} compact /> : <span />}
          <p className="text-xs text-nk-muted-aa sm:max-w-xs sm:text-right">{t('disclaimer.short')}</p>
        </div>
      )}
    </div>
  );
}
