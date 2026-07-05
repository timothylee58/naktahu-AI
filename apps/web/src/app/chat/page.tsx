'use client';

export const dynamic = 'force-dynamic';

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { useI18n } from '@/lib/i18n';
import { useSSEStream } from '@/lib/hooks/useSSEStream';
import type { Message } from '@/lib/types';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { ChatInput } from '@/components/chat/ChatInput';
import { PromptChips } from '@/components/chat/PromptChips';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { ThemeToggle } from '@/components/ThemeToggle';
import { useTheme } from '@/lib/theme';

let msgCounter = 0;
function makeId() {
  return `msg-${++msgCounter}-${Date.now()}`;
}

function ChatPageInner() {
  const { t, locale } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const { user, accessToken } = useSupabaseSession();
  const searchParams = useSearchParams();

  const [messages, setMessages] = useState<Message[]>([]);
  const [thinkingId, setThinkingId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [injectedQuery, setInjectedQuery] = useState(() => searchParams.get('q') ?? '');

  const q = searchParams.get('q');
  useEffect(() => {
    if (q !== null) setInjectedQuery(q);
    else setInjectedQuery('');
  }, [q]);
  const lastUserQuery = useRef<string>('');

  const bottomRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const conversationChars = useMemo(
    () => messages.reduce((sum, msg) => sum + msg.content.length, 0),
    [messages],
  );

  const {
    tokens,
    citations,
    metadata,
    suggestions,
    isStreaming,
    error,
    startStream,
    reset,
  } = useSSEStream({ language: locale, accessToken: accessToken ?? undefined });

  const streamingAssistantId = useRef<string | null>(null);
  const bubbleCreated = useRef(false);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, tokens, scrollToBottom]);

  // When first token arrives, remove ThinkingIndicator and show streaming bubble
  useEffect(() => {
    if (tokens?.length > 0 && !bubbleCreated.current) {
      bubbleCreated.current = true;
      if (thinkingId) {
        setMessages((prev) => prev.filter((m) => m.id !== thinkingId));
        setThinkingId(null);
      }
      const assistantId = makeId();
      streamingAssistantId.current = assistantId;
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          tokens: [...tokens],
          citations: [],
          confidence: null,
          isStreaming: true,
        },
      ]);
    }
  }, [tokens, thinkingId]);

  // Subsequent tokens — update the live streaming bubble
  useEffect(() => {
    if (tokens.length > 1 && streamingAssistantId.current) {
      const id = streamingAssistantId.current;
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, tokens: [...tokens] } : m)),
      );
    }
  }, [tokens]);

  // Streaming done — finalise message with citations, confidence
  useEffect(() => {
    if (!isStreaming && streamingAssistantId.current) {
      const id = streamingAssistantId.current;
      const confidence =
        (metadata?.confidence as number | undefined) ?? null;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id
            ? {
                ...m,
                content: tokens.join(''),
                tokens: [],
                citations,
                confidence,
                isStreaming: false,
                query: lastUserQuery.current,
                domain: metadata?.domain,
                language: metadata?.detectedLanguage,
                suggestions,
              }
            : m,
        ),
      );
      streamingAssistantId.current = null;
    }
  }, [isStreaming]); // eslint-disable-line react-hooks/exhaustive-deps

  // Show error as assistant message
  useEffect(() => {
    if (error) {
      const id = thinkingId ?? streamingAssistantId.current;
      if (id) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === id
              ? {
                  ...m,
                  content: t('error.stream'),
                  tokens: [],
                  isStreaming: false,
                }
              : m,
          ),
        );
        setThinkingId(null);
        streamingAssistantId.current = null;
      }
    }
  }, [error]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = useCallback(
    (query: string) => {
      lastUserQuery.current = query;
      reset();
      streamingAssistantId.current = null;
      bubbleCreated.current = false;

      const userMsg: Message = {
        id: makeId(),
        role: 'user',
        content: query,
        tokens: [],
        citations: [],
        confidence: null,
        isStreaming: false,
      };

      const thinkId = makeId();
      setThinkingId(thinkId);
      const thinkMsg: Message = {
        id: thinkId,
        role: 'assistant',
        content: '',
        tokens: [],
        citations: [],
        confidence: null,
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, thinkMsg]);
      startStream(query, locale);
    },
    [reset, startStream, locale],
  );

  const handleRegenerate = useCallback(() => {
    if (!lastUserQuery.current) return;
    // Remove the last assistant message before re-sending
    setMessages((prev) => {
      const lastAssistantIdx = [...prev].reverse().findIndex((m) => m.role === 'assistant');
      if (lastAssistantIdx === -1) return prev;
      const idx = prev.length - 1 - lastAssistantIdx;
      return prev.filter((_, i) => i !== idx);
    });
    handleSend(lastUserQuery.current);
  }, [handleSend]);

  const handleSelectHistoryQuery = useCallback((query: string) => {
    setInjectedQuery(query);
    setSidebarOpen(false);
  }, []);

  const handleChipSelect = useCallback((query: string) => {
    setInjectedQuery(query);
  }, []);

  const detectedLang =
    (metadata?.detectedLanguage as string | undefined) ?? undefined;

  const showChips = messages.length === 0 && !isStreaming;

  const pageBg = isDark ? 'bg-[#0A0F1E]' : 'bg-zinc-50/50';
  const headerClass = isDark
    ? 'border-white/10 bg-[#0A0F1E]/90 text-white'
    : 'border-zinc-100 bg-white/90 text-zinc-900';
  const headerSub = isDark ? 'text-zinc-400' : 'text-zinc-500';
  const menuBtn = isDark
    ? 'text-zinc-400 hover:bg-white/10 hover:text-zinc-200'
    : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800';
  const emptyTitle = isDark ? 'text-zinc-200' : 'text-zinc-700';
  const emptyDesc = isDark ? 'text-zinc-500' : 'text-zinc-400';
  const domainPill = isDark
    ? 'text-blue-300 bg-blue-500/10 border-blue-500/30'
    : 'text-blue-600 bg-blue-50 border-blue-100';
  const inputBarClass = isDark
    ? 'border-white/10 bg-[#0A0F1E]/90'
    : 'border-zinc-100 bg-white/90';
  const hintClass = isDark ? 'text-zinc-500' : 'text-zinc-400';

  return (
    <div className={`flex h-full ${pageBg}`}>
      <AppSidebar
        variant={isDark ? 'dark' : 'light'}
        isMobileOpen={sidebarOpen}
        onMobileClose={() => setSidebarOpen(false)}
        showHistory
        user={user}
        accessToken={accessToken}
        onSelectQuery={handleSelectHistoryQuery}
      />

      <div className="flex flex-col flex-1 min-w-0 h-full">
      <header className={`flex-shrink-0 flex items-center justify-between px-4 py-3 border-b backdrop-blur-md sticky top-0 z-10 shadow-sm ${headerClass}`}>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label={t('header.menu')}
            className={`p-1.5 rounded-lg transition-colors lg:hidden ${menuBtn}`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-5 h-5"
            >
              <path
                fillRule="evenodd"
                d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM2 10a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
                clipRule="evenodd"
              />
            </svg>
          </button>

          <Link href="/" className="flex flex-col">
            <span className="text-base font-bold tracking-tight">
              {t('header.title')}
            </span>
            <span className={`text-xs ${headerSub}`}>{t('header.subtitle')}</span>
          </Link>
        </div>
        <ThemeToggle variant={isDark ? 'dark' : 'light'} />
      </header>

      {/* message list */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto px-4 py-6 space-y-5 scroll-smooth"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-5 select-none px-6">
            {/* Logo mark */}
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center shadow-lg shadow-blue-900/20">
              <svg viewBox="0 0 32 32" className="w-9 h-9" fill="none" aria-hidden>
                <circle cx="16" cy="16" r="12" fill="white" fillOpacity="0.15" />
                <path d="M9 12h14M9 16h9M9 20h11" stroke="white" strokeWidth="2.2" strokeLinecap="round" />
              </svg>
            </div>
            <div className="flex flex-col gap-1">
              <p className={`text-lg font-bold ${emptyTitle}`}>NakTahu AI</p>
              <p className={`text-sm max-w-[260px] leading-relaxed ${emptyDesc}`}>{t('chat.empty')}</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 max-w-xs">
              {(['tax', 'epf', 'business', 'immigration'] as const).map((d) => (
                <span key={d} className={`text-[11px] font-medium border rounded-full px-2.5 py-1 ${domainPill}`}>
                  {t(`domain.${d}`)}
                </span>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg) =>
          msg.role === 'user' ? (
            <ChatBubble key={msg.id} role="user" content={msg.content} />
          ) : (
            <ChatBubble
              key={msg.id}
              role="assistant"
              content={msg.content}
              tokens={msg.tokens ?? []}
              citations={msg.citations ?? []}
              confidence={msg.confidence}
              isStreaming={msg.isStreaming}
              isThinking={msg.isStreaming && (msg.tokens?.length ?? 0) === 0}
              onRegenerate={!msg.isStreaming ? handleRegenerate : undefined}
              query={msg.query}
              domain={msg.domain}
              language={msg.language}
              accessToken={accessToken ?? undefined}
              suggestions={msg.suggestions ?? []}
              onSuggestionSelect={handleChipSelect}
            />
          ),
        )}
        <div ref={bottomRef} />
      </div>

      <div className={`flex-shrink-0 border-t backdrop-blur-md px-4 pt-3 pb-safe pb-3 flex flex-col gap-2 ${inputBarClass}`}>
        {showChips && (
          <PromptChips onSelect={handleChipSelect} disabled={isStreaming} variant={isDark ? 'dark' : 'light'} />
        )}
        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming}
          detectedLanguage={detectedLang}
          inject={injectedQuery}
          conversationChars={conversationChars}
          variant={isDark ? 'dark' : 'light'}
        />
        <p className={`hidden sm:block text-center text-[10px] ${hintClass}`}>
          {t('chat.keyboard_hint')}
        </p>
      </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense>
      <ChatPageInner />
    </Suspense>
  );
}
