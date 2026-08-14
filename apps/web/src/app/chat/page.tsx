'use client';

export const dynamic = 'force-dynamic';

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { useSearchParams } from 'next/navigation';
import { useSWRConfig } from 'swr';
import { useI18n } from '@/lib/i18n';
import { useSSEStream } from '@/lib/hooks/useSSEStream';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import type { Message } from '@/lib/types';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { ChatInput } from '@/components/chat/ChatInput';
import { PromptChips } from '@/components/chat/PromptChips';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { useTheme } from '@/lib/theme';
import { canAccessHistory } from '@/lib/auth-plan';
import { sidebarHistoryKey, HISTORY_RESTORE_STORAGE_KEY, type HistoryEntry } from '@/lib/history';

let msgCounter = 0;
function makeId() {
  return `msg-${++msgCounter}-${Date.now()}`;
}

function ChatPageInner() {
  const { t, locale } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const { user, userId, accessToken } = useSupabaseSession();
  const { mutate: globalMutate } = useSWRConfig();
  const searchParams = useSearchParams();

  const [messages, setMessages] = useState<Message[]>([]);
  const [thinkingId, setThinkingId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [injectedQuery, setInjectedQuery] = useState(() => searchParams.get('q') ?? '');
  // A message sent while the current answer is still streaming — held here
  // and auto-fired once isStreaming flips false, instead of blocking input
  // entirely until the in-flight answer completes.
  const [queuedQuery, setQueuedQuery] = useState<string | null>(null);

  const q = searchParams.get('q');
  useEffect(() => {
    if (q !== null) setInjectedQuery(q);
    else setInjectedQuery('');
  }, [q]);
  const lastUserQuery = useRef<string>('');
  const wasStreaming = useRef(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  // Tracked as a ref (not state) so the auto-scroll effect can read it
  // synchronously without re-running on every scroll pixel — only the
  // "jump to latest" button's visibility needs to trigger a re-render.
  const isAtBottomRef = useRef(true);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);

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
    stop,
  } = useSSEStream({ language: locale, accessToken: accessToken ?? undefined });

  const streamingAssistantId = useRef<string | null>(null);
  const bubbleCreated = useRef(false);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    isAtBottomRef.current = true;
    setShowJumpToLatest(false);
  }, []);

  const handleScroll = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distanceFromBottom < 120;
    isAtBottomRef.current = atBottom;
    setShowJumpToLatest(!atBottom);
  }, []);

  // Auto-scroll only while the user is already at (or near) the bottom —
  // if they've scrolled up to re-read something mid-answer, new tokens
  // must not yank them back down.
  useEffect(() => {
    if (isAtBottomRef.current) scrollToBottom();
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
                agencyContact: metadata?.agency_contact,
              }
            : m,
        ),
      );
      streamingAssistantId.current = null;
    }
  }, [isStreaming]); // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh sidebar history after a completed answer (server persists summary on stream end).
  useEffect(() => {
    if (wasStreaming.current && !isStreaming && userId && user && canAccessHistory(user)) {
      const timer = window.setTimeout(() => {
        void globalMutate(sidebarHistoryKey(userId));
      }, 600);
      return () => window.clearTimeout(timer);
    }
    wasStreaming.current = isStreaming;
    return undefined;
  }, [isStreaming, userId, user, globalMutate]);

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
                  isError: true,
                  query: lastUserQuery.current,
                }
              : m,
          ),
        );
        setThinkingId(null);
        streamingAssistantId.current = null;
      }
    }
  }, [error]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNewChat = useCallback(() => {
    reset();
    setMessages([]);
    setThinkingId(null);
    setInjectedQuery('');
    setQueuedQuery(null);
    lastUserQuery.current = '';
    streamingAssistantId.current = null;
    bubbleCreated.current = false;
    isAtBottomRef.current = true;
    setShowJumpToLatest(false);
  }, [reset]);

  const handleSend = useCallback(
    (query: string) => {
      if (isStreaming) {
        // Don't reset()/abort the in-flight answer — hold this one until
        // it finishes, then fire it automatically (see the dequeue effect).
        setQueuedQuery(query);
        return;
      }

      lastUserQuery.current = query;
      reset();
      streamingAssistantId.current = null;
      bubbleCreated.current = false;
      isAtBottomRef.current = true;

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
    [isStreaming, reset, startStream, locale],
  );

  // Fire a queued message once the current stream actually finishes.
  useEffect(() => {
    if (!isStreaming && queuedQuery) {
      const q = queuedQuery;
      setQueuedQuery(null);
      handleSend(q);
    }
  }, [isStreaming, queuedQuery, handleSend]);

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

  const handleStop = useCallback(() => {
    stop();
    // If the abort lands before any token arrived, the finalise-on-
    // isStreaming-false effect never fires (streamingAssistantId is still
    // null — no bubble was ever created to finalise) — the "thinking"
    // placeholder would otherwise sit there forever. Clear it directly.
    if (!bubbleCreated.current && thinkingId) {
      setMessages((prev) => prev.filter((m) => m.id !== thinkingId));
      setThinkingId(null);
    }
  }, [stop, thinkingId]);

  const handleSelectHistoryQuery = useCallback((entry: HistoryEntry) => {
    setSidebarOpen(false);
    // Rows written before migration 028 have no stored response_text — fall
    // back to the old re-prompt behavior since there's nothing to show back.
    const responseText = entry.response_text;
    if (!responseText) {
      setInjectedQuery(entry.query);
      return;
    }
    setMessages((prev) => [
      ...prev,
      {
        id: makeId(),
        role: 'user',
        content: entry.query,
        tokens: [],
        citations: [],
        confidence: null,
        isStreaming: false,
      },
      {
        id: makeId(),
        role: 'assistant',
        content: responseText,
        tokens: [],
        citations: (entry.citations as Message['citations']) ?? [],
        confidence: entry.confidence ?? null,
        isStreaming: false,
        query: entry.query,
        domain: entry.domain,
        language: entry.language,
        suggestions: entry.suggestions ?? [],
        agencyContact: entry.agency_contact ?? undefined,
      },
    ]);
  }, []);

  // Pick up a history entry handed off from /history's "click to view"
  // (see HISTORY_RESTORE_STORAGE_KEY) — sessionStorage instead of a URL
  // param since response_text can be long.
  useEffect(() => {
    const raw = sessionStorage.getItem(HISTORY_RESTORE_STORAGE_KEY);
    if (!raw) return;
    sessionStorage.removeItem(HISTORY_RESTORE_STORAGE_KEY);
    try {
      handleSelectHistoryQuery(JSON.parse(raw) as HistoryEntry);
    } catch {
      // Malformed/stale payload — ignore rather than crash the page.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleChipSelect = useCallback((query: string) => {
    setInjectedQuery(query);
  }, []);

  const detectedLang =
    (metadata?.detectedLanguage as string | undefined) ?? undefined;

  const showChips = messages.length === 0 && !isStreaming;

  const pageBg = isDark ? 'bg-[#12151C]' : 'bg-zinc-50/50';
  const headerClass = isDark
    ? 'border-white/10 bg-[#12151C]/90 text-white'
    : 'border-zinc-100 bg-white/90 text-zinc-900';
  const headerSub = isDark ? 'text-zinc-400' : 'text-zinc-500';
  const menuBtn = isDark
    ? 'text-zinc-400 hover:bg-white/10 hover:text-zinc-200'
    : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800';
  const emptyTitle = isDark ? 'text-zinc-200' : 'text-zinc-700';
  const emptyDesc = isDark ? 'text-zinc-500' : 'text-zinc-400';
  const inputBarClass = isDark
    ? 'border-white/10 bg-[#12151C]/90'
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
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
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
        {messages.length > 0 && (
          <button
            type="button"
            onClick={handleNewChat}
            className={`flex items-center gap-1.5 text-xs font-semibold rounded-full px-3 py-1.5 transition-colors ${menuBtn}`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
            </svg>
            <span className="hidden sm:inline">{t('chat.new_chat')}</span>
          </button>
        )}
      </header>

      {/* message list */}
      <div className="relative flex-1 min-h-0">
      <div
        ref={listRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto px-4 py-6 space-y-5 scroll-smooth"
      >
        <div className="max-w-3xl mx-auto w-full space-y-5">
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: 'easeOut' }}
            className="flex flex-col items-center justify-center text-center gap-5 select-none px-6 py-16"
          >
            {/* Logo mark */}
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-nk-official to-nk-official-dim flex items-center justify-center shadow-lg shadow-blue-900/30 ring-1 ring-white/10">
              <svg viewBox="0 0 32 32" className="w-9 h-9" fill="none" aria-hidden>
                <circle cx="16" cy="16" r="12" fill="white" fillOpacity="0.15" />
                <path d="M9 12h14M9 16h9M9 20h11" stroke="white" strokeWidth="2.2" strokeLinecap="round" />
              </svg>
            </div>
            <div className="flex flex-col gap-1">
              <p className={`text-lg font-bold ${emptyTitle}`}>NakTahu AI</p>
              <p className={`text-sm max-w-[260px] leading-relaxed ${emptyDesc}`}>{t('chat.empty')}</p>
            </div>
          </motion.div>
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
              agencyContact={msg.agencyContact}
              isError={msg.isError}
            />
          ),
        )}
        <div ref={bottomRef} />
        </div>
      </div>

      {showJumpToLatest && (
        <button
          type="button"
          onClick={scrollToBottom}
          aria-label={t('chat.jump_to_latest')}
          className={`absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 text-xs font-semibold rounded-full px-3 py-1.5 shadow-md transition-colors ${
            isDark
              ? 'bg-[#141929] text-zinc-200 border border-white/10 hover:bg-white/10'
              : 'bg-white text-zinc-700 border border-zinc-200 hover:bg-zinc-50'
          }`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
            <path fillRule="evenodd" d="M10 3a.75.75 0 0 1 .75.75v10.638l3.96-4.158a.75.75 0 1 1 1.08 1.04l-5.25 5.5a.75.75 0 0 1-1.08 0l-5.25-5.5a.75.75 0 1 1 1.08-1.04l3.96 4.158V3.75A.75.75 0 0 1 10 3Z" clipRule="evenodd" />
          </svg>
          {t('chat.jump_to_latest')}
        </button>
      )}
      </div>

      <div className={`flex-shrink-0 border-t backdrop-blur-md px-4 pt-3 pb-safe pb-3 shadow-[0_-4px_20px_rgba(0,0,0,0.03)] ${inputBarClass}`}>
        <div className="max-w-3xl mx-auto w-full flex flex-col gap-2">
        {showChips && (
          <PromptChips onSelect={handleChipSelect} disabled={isStreaming} variant={isDark ? 'dark' : 'light'} />
        )}
        {queuedQuery && (
          <div
            className={`flex items-center gap-2 text-xs rounded-lg px-3 py-1.5 ${
              isDark ? 'bg-white/5 text-zinc-300' : 'bg-zinc-100 text-zinc-600'
            }`}
          >
            <span className="font-semibold flex-shrink-0 locale-nowrap">{t('chat.queued')}:</span>
            <span className="truncate flex-1">{queuedQuery}</span>
            <button
              type="button"
              onClick={() => setQueuedQuery(null)}
              aria-label={t('auth.error.dismiss')}
              className={`flex-shrink-0 p-0.5 rounded transition-colors ${isDark ? 'hover:bg-white/10' : 'hover:bg-zinc-200'}`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
              </svg>
            </button>
          </div>
        )}
        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming}
          onStop={handleStop}
          detectedLanguage={detectedLang}
          inject={injectedQuery}
          conversationChars={conversationChars}
          variant={isDark ? 'dark' : 'light'}
        />
        <p className={`hidden sm:block text-center text-[10px] ${hintClass}`}>
          {t('chat.keyboard_hint')}
        </p>
        {/* The not-official-government-advice disclaimer previously appeared
            only on landing, /about and shared-answer permalinks — i.e.
            everywhere EXCEPT the surface where someone actually asks a tax
            or immigration question. Persistent (not hidden on mobile, not
            dismissible) because it's the compliance-relevant line, and
            reusing landing.hero.disclaimer_note so the wording can't drift
            between surfaces. */}
        <p className={`text-center text-[10px] leading-snug locale-text-balance ${hintClass}`}>
          {t('landing.hero.disclaimer_note')}
        </p>
        </div>
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
