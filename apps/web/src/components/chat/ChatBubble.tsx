'use client';

import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgencyContact, Citation } from '@/lib/types';
import { useI18n } from '@/lib/i18n';
import { AgencyContactCard } from './AgencyContactCard';
import { CitationChip } from './CitationChip';
import { StreamingText } from './StreamingText';
import { ThinkingIndicator } from './ThinkingIndicator';
import { ResponseActions } from './ResponseActions';
import { SuggestionChips } from './SuggestionChips';

interface UserBubbleProps {
  role: 'user';
  content: string;
}

interface AssistantBubbleProps {
  role: 'assistant';
  content: string;
  tokens: string[];
  citations: Citation[];
  confidence: number | null;
  isStreaming: boolean;
  isThinking?: boolean;
  onRegenerate?: () => void;
  query?: string;
  domain?: string;
  language?: string;
  accessToken?: string;
  suggestions?: string[];
  onSuggestionSelect?: (query: string) => void;
  agencyContact?: AgencyContact;
  isError?: boolean;
}

type ChatBubbleProps = UserBubbleProps | AssistantBubbleProps;

const LOW_CONFIDENCE_THRESHOLD = 0.4;

const spring = { duration: 0.28, ease: [0.16, 1, 0.3, 1] } as const;

export function ChatBubble(props: ChatBubbleProps) {
  const { t } = useI18n();

  if (props.role === 'user') {
    return (
      <div className="flex justify-end">
        <motion.div
          initial={{ opacity: 0, y: 8, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={spring}
          className="max-w-[75%] bg-nk-official text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed shadow-md shadow-blue-900/10"
        >
          {props.content}
        </motion.div>
      </div>
    );
  }

  const { content, tokens, citations, confidence, isStreaming, isThinking = false, onRegenerate, query, domain, language, accessToken, suggestions = [], onSuggestionSelect, agencyContact, isError = false } = props;
  const hasLowConfidence = confidence !== null && confidence < LOW_CONFIDENCE_THRESHOLD;

  return (
    <div className="flex justify-start gap-2.5">
      {/* Avatar */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-nk-official to-nk-official-dim flex items-center justify-center mt-1 shadow-sm">
        <span className="text-white text-[10px] font-bold">AI</span>
      </div>

      <div className="max-w-[80%] flex flex-col gap-2">
        <motion.div
          initial={{ opacity: 0, y: 8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={spring}
          className={
            isError
              ? 'flex items-start gap-2 bg-red-50 border border-red-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-red-700 dark:bg-red-500/10 dark:border-red-500/30 dark:text-red-300'
              : 'bg-white border border-zinc-100 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-zinc-800 shadow-sm ring-1 ring-zinc-900/5 dark:bg-white/5 dark:border-white/10 dark:text-zinc-100 dark:ring-white/5'
          }
        >
          {isError ? (
            <>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 flex-shrink-0 mt-0.5">
                <path fillRule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
              </svg>
              <span>{content}</span>
            </>
          ) : isThinking ? (
            <ThinkingIndicator />
          ) : isStreaming || (tokens?.length ?? 0) > 0 ? (
            <StreamingText tokens={tokens ?? []} isStreaming={isStreaming} />
          ) : (
            <span className="chat-content text-sm leading-relaxed">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </span>
          )}
        </motion.div>

        {isError && onRegenerate && (
          <button
            type="button"
            onClick={onRegenerate}
            className="self-start flex items-center gap-1.5 text-xs font-semibold text-red-700 hover:text-red-800 dark:text-red-300 dark:hover:text-red-200 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
              <path fillRule="evenodd" d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.449-.39Zm1.23-3.723a.75.75 0 0 0 .219-.53V2.929a.75.75 0 0 0-1.5 0V5.36l-.31-.31A7 7 0 0 0 3.239 8.188a.75.75 0 1 0 1.448.389A5.5 5.5 0 0 1 13.89 6.11l.311.31h-2.432a.75.75 0 0 0 0 1.5h4.243a.75.75 0 0 0 .53-.219Z" clipRule="evenodd" />
            </svg>
            {t('error.retry')}
          </button>
        )}

        {!isStreaming && !isThinking && !isError && agencyContact && (
          <AgencyContactCard contact={agencyContact} />
        )}

        {/* Action buttons — only after streaming completes */}
        {!isStreaming && !isThinking && !isError && content && (
          <ResponseActions
            content={content}
            onRegenerate={onRegenerate}
            isStreaming={isStreaming}
            query={query}
            domain={domain}
            language={language}
            citations={citations}
            confidence={confidence}
            accessToken={accessToken}
          />
        )}

        {!isError && hasLowConfidence && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5 dark:text-amber-300 dark:bg-amber-500/10 dark:border-amber-500/30"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 flex-shrink-0">
              <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 5Zm0 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
            </svg>
            <span>{t('chat.warning.low_confidence')}</span>
          </motion.div>
        )}

        {citations.length > 0 && (
          <motion.div
            className="flex flex-wrap gap-1.5"
            initial="hidden"
            animate="visible"
            variants={{
              hidden: {},
              visible: { transition: { staggerChildren: 0.07, delayChildren: 0.1 } },
            }}
          >
            {citations.map((c, i) => (
              <motion.div
                key={i}
                variants={{ hidden: { opacity: 0, y: 6 }, visible: { opacity: 1, y: 0 } }}
                transition={{ duration: 0.2 }}
              >
                <CitationChip citation={c} index={i + 1} />
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Suggestions — only show after streaming completes and if we have suggestions */}
        {!isStreaming && !isThinking && suggestions.length > 0 && onSuggestionSelect && (
          <SuggestionChips
            suggestions={suggestions}
            onSelect={onSuggestionSelect}
            disabled={false}
          />
        )}
      </div>
    </div>
  );
}
