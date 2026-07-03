'use client';

export const dynamic = 'force-dynamic';

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';
import { useSSEStream } from '@/lib/hooks/useSSEStream';
import type { Message } from '@/lib/types';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { ChatInput } from '@/components/chat/ChatInput';
import { PromptChips } from '@/components/chat/PromptChips';
import { AuthButton } from '@/components/auth/AuthButton';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { LangToggle } from '@/components/LangToggle';

let msgCounter = 0;
function makeId() {
  return `msg-${++msgCounter}-${Date.now()}`;
}

function ChatPageInner() {
  const { t, locale } = useI18n();
  const supabase = useMemo(() => createClient(), []);
  const searchParams = useSearchParams();

  const [messages, setMessages] = useState<Message[]>([]);
  const [thinkingId, setThinkingId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [injectedQuery, setInjectedQuery] = useState(() => searchParams.get('q') ?? '');

  // Hydrate the desktop collapse preference after mount (avoids SSR mismatch)
  useEffect(() => {
    if (localStorage.getItem('naktahu_sidebar_collapsed') === '1') {
      setSidebarCollapsed(true);
    }
  }, []);

  const toggleSidebarCollapsed = useCallback(() => {
    setSidebarCollapsed((c) => {
      const next = !c;
      localStorage.setItem('naktahu_sidebar_collapsed', next ? '1' : '0');
      return next;
    });
  }, []);

  const q = searchParams.get('q');
  useEffect(() => {
    if (q !== null) setInjectedQuery(q);
    else setInjectedQuery('');
  }, [q]);
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const lastUserQuery = useRef<string>('');

  const bottomRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Auth state
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null);
      setAccessToken(data.session?.access_token ?? null);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setAccessToken(session?.access_token ?? null);
    });

    return () => subscription.unsubscribe();
  }, [supabase]);

  const {
    tokens,
    citations,
    metadata,
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

  const handleNewChat = useCallback(() => {
    reset();
    streamingAssistantId.current = null;
    bubbleCreated.current = false;
    lastUserQuery.current = '';
    setThinkingId(null);
    setMessages([]);
    setInjectedQuery('');
    setSidebarOpen(false);
  }, [reset]);

  const detectedLang =
    (metadata?.detectedLanguage as string | undefined) ?? undefined;

  const showChips = messages.length === 0 && !isStreaming;

  return (
    <div className="flex h-full bg-zinc-50/50">
      {/* Left panel — persistent on desktop (collapsible), full-page overlay on mobile */}
      <ChatSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebarCollapsed}
        user={user}
        accessToken={accessToken}
        onSelectQuery={handleSelectHistoryQuery}
        onNewChat={handleNewChat}
      />

      {/* Main column */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* header */}
        <header className="flex-shrink-0 flex items-center justify-between gap-3 px-4 py-3 border-b border-zinc-100 bg-white/90 backdrop-blur-md sticky top-0 z-10 shadow-sm">
          <div className="flex items-center gap-2 min-w-0">
            {/* sidebar toggle — mobile only */}
            <button
              onClick={() => setSidebarOpen(true)}
              aria-label={t('header.history')}
              className="md:hidden p-1.5 rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 transition-colors flex-shrink-0"
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

            {/* expand sidebar — desktop only, when the panel is collapsed */}
            {sidebarCollapsed && (
              <button
                onClick={toggleSidebarCollapsed}
                aria-label={t('sidebar.expand')}
                title={t('sidebar.expand')}
                className="hidden md:inline-flex p-1.5 rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 transition-colors flex-shrink-0"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                  <path fillRule="evenodd" d="M4.25 3A2.25 2.25 0 0 0 2 5.25v9.5A2.25 2.25 0 0 0 4.25 17h11.5A2.25 2.25 0 0 0 18 14.75v-9.5A2.25 2.25 0 0 0 15.75 3H4.25ZM8 4.5v11H4.25a.75.75 0 0 1-.75-.75v-9.5a.75.75 0 0 1 .75-.75H8Zm1.5 0h6.25a.75.75 0 0 1 .75.75v9.5a.75.75 0 0 1-.75.75H9.5v-11Z" clipRule="evenodd" />
                </svg>
              </button>
            )}

            <Link href="/" className="flex flex-col min-w-0">
              <span className="text-base font-bold text-zinc-900 tracking-tight truncate">
                {t('header.title')}
              </span>
              <span className="text-xs text-zinc-500 truncate">{t('header.subtitle')}</span>
            </Link>
          </div>

          {/* Auth + language live in the sidebar footer on desktop */}
          <div className="flex md:hidden items-center gap-2 flex-shrink-0">
            <AuthButton />
            <LangToggle variant="light" />
          </div>
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
              <p className="text-lg font-bold text-zinc-700">NakTahu AI</p>
              <p className="text-sm text-zinc-400 max-w-[280px] leading-relaxed">{t('chat.empty')}</p>
            </div>
            {/* Quick domain pills */}
            <div className="flex flex-wrap justify-center gap-2 max-w-sm">
              {(['tax', 'epf', 'business', 'immigration'] as const).map((d) => (
                <span key={d} className="text-[11px] font-medium text-blue-600 bg-blue-50 border border-blue-100 rounded-full px-2.5 py-1 whitespace-nowrap">
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
            />
          ),
        )}
        <div ref={bottomRef} />
      </div>

      {/* input bar */}
      <div className="flex-shrink-0 border-t border-zinc-100 bg-white/90 backdrop-blur-md px-4 pt-3 pb-safe pb-3 flex flex-col gap-2">
        {showChips && (
          <PromptChips onSelect={handleChipSelect} disabled={isStreaming} />
        )}
        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming}
          detectedLanguage={detectedLang}
          inject={injectedQuery}
        />
          <p className="hidden sm:block text-center text-[10px] text-zinc-400">
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
