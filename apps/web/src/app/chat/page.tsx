'use client';

export const dynamic = 'force-dynamic';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import type { User } from '@supabase/supabase-js';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n';
import { useSSEStream } from '@/lib/hooks/useSSEStream';
import type { Message } from '@/lib/types';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { ChatInput } from '@/components/chat/ChatInput';
import { AuthButton } from '@/components/auth/AuthButton';
import { HistorySidebar } from '@/components/history/HistorySidebar';

let msgCounter = 0;
function makeId() {
  return `msg-${++msgCounter}-${Date.now()}`;
}

export default function ChatPage() {
  const { t, locale, setLocale } = useI18n();
  const supabase = useMemo(() => createClient(), []);

  const [messages, setMessages] = useState<Message[]>([]);
  const [thinkingId, setThinkingId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [injectedQuery, setInjectedQuery] = useState('');
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);

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

  const handleSelectHistoryQuery = useCallback((query: string) => {
    setInjectedQuery(query);
    setSidebarOpen(false);
  }, []);

  const detectedLang =
    (metadata?.detectedLanguage as string | undefined) ?? undefined;

  return (
    <div className="flex flex-col h-full">
      {/* History sidebar */}
      <HistorySidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        user={user}
        accessToken={accessToken}
        onSelectQuery={handleSelectHistoryQuery}
      />

      {/* header */}
      <header className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-zinc-200 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-2">
          {/* sidebar toggle */}
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label={t('header.history')}
            className="p-1.5 rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 transition-colors"
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
            <span className="text-base font-bold text-zinc-900 tracking-tight">
              {t('header.title')}
            </span>
            <span className="text-xs text-zinc-500">{t('header.subtitle')}</span>
          </Link>
        </div>

        <div className="flex items-center gap-2">
          <AuthButton />
          <button
            onClick={() => setLocale(locale === 'ms' ? 'en' : 'ms')}
            className="text-xs font-semibold bg-zinc-100 hover:bg-zinc-200 text-zinc-700 rounded-full px-3 py-1.5 transition-colors"
          >
            {t('header.lang_toggle')}
          </button>
        </div>
      </header>

      {/* message list */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto px-4 py-6 space-y-4 scroll-smooth"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3 text-zinc-400 select-none">
            <span className="text-4xl">🇲🇾</span>
            <p className="text-sm max-w-xs">{t('chat.empty')}</p>
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
              tokens={msg.tokens}
              citations={msg.citations}
              confidence={msg.confidence}
              isStreaming={msg.isStreaming}
              isThinking={msg.isStreaming && msg.tokens.length === 0}
            />
          ),
        )}
        <div ref={bottomRef} />
      </div>

      {/* input bar */}
      <div className="flex-shrink-0 border-t border-zinc-100 bg-white px-4 py-3">
        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming}
          detectedLanguage={detectedLang}
          inject={injectedQuery}
        />
      </div>
    </div>
  );
}
