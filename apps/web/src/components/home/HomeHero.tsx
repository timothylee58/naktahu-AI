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
import { StatusPills } from '@/components/prompt/StatusPills';
import { SuggestionChips } from '@/components/prompt/SuggestionChips';
import { usePromptBox } from '@/components/prompt/usePromptBox';
import { CategoryTiles } from './CategoryTiles';

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
  const selectTile = (id: CategoryId) => {
    selectCategory(id);
    inputRef.current?.focus();
    inputRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  };
  const pickChip = (text: string) => {
    source.current = 'chip';
    box.fill(text);
    inputRef.current?.focus();
  };

  const hint = box.value.trim()
    ? `${t(`box.langDetected.${answerLang}`)} · ${t('box.hint.keys')}`
    : t('box.hint.idle');

  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col items-center gap-5 px-4 pb-10 pt-12 text-center sm:px-6 sm:pt-16">
      <h1 className="font-display text-[clamp(32px,5.5vw,52px)] font-extrabold leading-[1.08] tracking-[-0.02em] text-nk-ink locale-text-balance">
        {t('home.title')}
      </h1>
      <StatusPills lang={badge} />

      <div className="mt-4 flex w-full flex-col gap-2.5 sm:mt-6">
        <CategoryTabs active={category} onSelect={selectCategory} />
        <SuggestionChips category={category} onSelect={pickChip} disabled={exhausted} />
      </div>

      <div className="flex w-full flex-col gap-3">
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
      </div>

      <div className="flex w-full flex-col items-center justify-between gap-3 sm:flex-row sm:items-start">
        {quota && !exhausted ? <QuotaMeter quota={quota} onLogin={login} /> : <span />}
        {exhausted ? (
          <div className="flex w-full flex-wrap items-center justify-center gap-3 sm:justify-start">
            <Button type="button" size="lg" onClick={login}>
              {t('header.login')}
            </Button>
            <button type="button" onClick={login} className="text-sm font-semibold text-nk-official-text underline underline-offset-2">
              {t('quota.register')}
            </button>
          </div>
        ) : (
          <p className="hidden text-xs text-nk-muted-aa sm:block" aria-live="polite">
            {hint}
          </p>
        )}
      </div>

      <p className="max-w-xl text-xs leading-normal text-nk-muted-aa locale-text-balance">{t('disclaimer.short')}</p>

      <section aria-labelledby="home-categories" className="mt-8 w-full text-left">
        <h2 id="home-categories" className="mb-5 font-display text-xl font-bold text-nk-ink sm:text-2xl">
          {t('section.categories')}
        </h2>
        <CategoryTiles active={category} onSelect={selectTile} />
      </section>
    </div>
  );
}
