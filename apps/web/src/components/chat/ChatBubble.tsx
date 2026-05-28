'use client';

import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Citation } from '@/lib/types';
import { CitationChip } from './CitationChip';
import { StreamingText } from './StreamingText';
import { ThinkingIndicator } from './ThinkingIndicator';
import { ResponseActions } from './ResponseActions';

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
}

type ChatBubbleProps = UserBubbleProps | AssistantBubbleProps;

const LOW_CONFIDENCE_THRESHOLD = 0.4;

const spring = { duration: 0.28, ease: [0.16, 1, 0.3, 1] } as const;

export function ChatBubble(props: ChatBubbleProps) {
  if (props.role === 'user') {
    return (
      <div className="flex justify-end">
        <motion.div
          initial={{ opacity: 0, y: 8, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={spring}
          className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed shadow-sm"
        >
          {props.content}
        </motion.div>
      </div>
    );
  }

  const { content, tokens, citations, confidence, isStreaming, isThinking = false, onRegenerate } = props;
  const hasLowConfidence = confidence !== null && confidence < LOW_CONFIDENCE_THRESHOLD;

  return (
    <div className="flex justify-start gap-2.5">
      {/* Avatar */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center mt-1 shadow-sm">
        <span className="text-white text-[10px] font-bold">AI</span>
      </div>

      <div className="max-w-[80%] flex flex-col gap-2">
        <motion.div
          initial={{ opacity: 0, y: 8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={spring}
          className="bg-white border border-zinc-100 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-zinc-800 shadow-sm ring-1 ring-zinc-900/5"
        >
          {isThinking ? (
            <ThinkingIndicator />
          ) : isStreaming || (tokens?.length ?? 0) > 0 ? (
            <StreamingText tokens={tokens ?? []} isStreaming={isStreaming} />
          ) : (
            <span className="chat-content text-sm leading-relaxed">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </span>
          )}
        </motion.div>

        {/* Action buttons — only after streaming completes */}
        {!isStreaming && !isThinking && content && (
          <ResponseActions content={content} onRegenerate={onRegenerate} isStreaming={isStreaming} />
        )}

        {hasLowConfidence && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5"
          >
            <span>⚠️</span>
            <span>Jawapan mungkin tidak tepat / Answer may be inaccurate</span>
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
                <CitationChip citation={c} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
    </div>
  );
}
