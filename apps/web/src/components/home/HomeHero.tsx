'use client';

import { useEffect, useRef, useState } from 'react';
import { useI18n } from '@/lib/i18n';
import { useDailyQuota } from '@/lib/hooks/useDailyQuota';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { useVoiceInput } from '@/lib/hooks/useVoiceInput';
import type { CategoryId } from '@/lib/categories';
import { detectLanguage } from '@/lib/prompt/detectLanguage';
import { savePending, type HandoffSource } from '@/lib/prompt/handoff';
import { Button } from '@/components/ui/button';
import { CategoryTabs } from '@/components/prompt/CategoryTabs';
import { PiiWarning } from '@/components/prompt/PiiWarning';
import { PromptBox } from '@/components/prompt/PromptBox';
import { QuotaMeter } from '@/components/prompt/QuotaMeter';
import { SuggestionChips } from '@/components/prompt/SuggestionChips';
import { usePromptBox } from '@/components/prompt/usePromptBox';

interface HomeHeroProps {
  /** Navigates to /chat (parent owns the route-change animation). */
  onEnterChat: (href: string) => void;
}

const VOICE_LOCALES = { ms: 'ms-MY', en: 'en-MY', zh: 'zh-MY' } as const;

export function HomeHero({ onEnterChat }: HomeHeroProps) {
  const { t, locale } = useI18n();
  const { supabase } = useSupabaseSession();
  const { quota } = useDailyQuota();
  const [category, setCategory] = useState<CategoryId>('tax');
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const source = useRef<HandoffSource>('typed');

  const send = (text: string) => {
    setSubmitting(true);
    const saved = savePending({ q: text, source: source.current, uiLocale: locale });
    // Private mode / blocked storage: fall back to the pre-fill-only ?q= path
    // rather than losing the question.
    onEnterChat(saved ? '/chat?from=home' : `/chat?q=${encodeURIComponent(text)}`);
  };
  const box = usePromptBox({ onSend: send });

  const voice = useVoiceInput({ language: VOICE_LOCALES[locale as keyof typeof VOICE_LOCALES] ?? 'ms-MY' });
  const { transcript } = voice;
  const { fill } = box;
  useEffect(() => {
    if (transcript) {
      source.current = 'voice';
      fill(transcript);
    }
  }, [transcript, fill]);

  const detected = detectLanguage(box.value);
  const uiLang = locale === 'zh' ? 'zh' : locale === 'en' ? 'en' : 'ms';
  const badge = { ms: 'BM', en: 'EN', zh: '中文' }[detected ?? uiLang];
  const answerLang = detected ?? uiLang;

  const exhausted = quota !== null && quota.used >= quota.limit;
  const login = () => {
    void supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  };

  const selectCategory = (id: CategoryId) => {
    setCategory(id);
    box.clear();
  };
  const pickChip = (text: string) => {
    source.current = 'chip';
    box.fill(text);
    inputRef.current?.focus();
  };

  // Only show the hint once there is something to say about the typed
  // question; the idle "pick a suggestion" line was one more grey row
  // competing with the box itself.
  const hint = box.value.trim() ? `${t(`box.langDetected.${answerLang}`)} · ${t('box.hint.keys')}` : '';

  // Box first, popular tasks underneath it (the USA.gov "search, then top
  // tasks" order). The status pills and the separate category-tile grid
  // were removed: the language badge already sits inside the box, the trust
  // strip carries the sourcing claim, and the tiles repeated the same four
  // categories as the tabs — two pickers for one choice made the hero crowded.
  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col items-center gap-6 px-4 pb-16 pt-14 text-center sm:px-6 sm:pt-20">
      <h1 className="font-display text-[clamp(32px,5.5vw,52px)] font-extrabold leading-[1.08] tracking-[-0.02em] text-nk-ink locale-text-balance">
        {t('home.title')}
      </h1>

      <div className="mt-2 flex w-full flex-col gap-3">
        <PromptBox
          variant="hero"
          value={box.value}
          onChange={(v) => {
            source.current = 'typed';
            box.type(v);
          }}
          onSubmit={box.submit}
          onClear={box.clear}
          placeholder={exhausted ? t('quota.exhausted') : t(`ph.${category}`)}
          languageBadge={badge}
          languageDetected={detected !== null && detected !== uiLang}
          status={exhausted ? 'disabled' : submitting ? 'submitting' : 'idle'}
          piiWarning={box.piiDetected}
          mic={{
            available: voice.available,
            listening: voice.isListening,
            onToggle: voice.isListening ? voice.stopListening : voice.startListening,
          }}
          inputRef={inputRef}
        />
        {box.piiDetected && <PiiWarning onRemove={box.stripPii} />}
        {submitting && (
          <p className="font-mono text-xs text-nk-official-text" role="status">
            {t('box.sending')}
          </p>
        )}
        <p className="min-h-4 text-right text-xs text-nk-muted-aa" aria-live="polite">
          {hint}
        </p>
      </div>

      <div className="flex w-full flex-col gap-2.5">
        <CategoryTabs active={category} onSelect={selectCategory} />
        <SuggestionChips category={category} onSelect={pickChip} disabled={exhausted} />
      </div>

      {(quota || exhausted) && (
        <div className="flex w-full flex-col items-center gap-3 sm:flex-row sm:justify-center">
          {quota && !exhausted && <QuotaMeter quota={quota} onLogin={login} />}
          {exhausted && (
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button type="button" size="lg" onClick={login}>
                {t('header.login')}
              </Button>
              <button type="button" onClick={login} className="text-sm font-semibold text-nk-official-text underline underline-offset-2">
                {t('quota.register')}
              </button>
            </div>
          )}
        </div>
      )}

      <p className="max-w-xl text-xs leading-normal text-nk-muted-aa locale-text-balance">{t('disclaimer.short')}</p>
    </div>
  );
}
