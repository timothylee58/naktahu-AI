'use client';

import { motion } from 'framer-motion';
import type { Citation } from '@/lib/types';
import { CitationChip } from './CitationChip';
import { StreamingText } from './StreamingText';
import { ThinkingIndicator } from './ThinkingIndicator';

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
}

type ChatBubbleProps = UserBubbleProps | AssistantBubbleProps;

const LOW_CONFIDENCE_THRESHOLD = 0.4;

export function ChatBubble(props: ChatBubbleProps) {
  if (props.role === 'user') {
    return (
      <div className="flex justify-end">
        <motion.div
          initial={{ opacity: 0, y: 6, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.2 }}
          className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm shadow-sm"
        >
          {props.content}
        </motion.div>
      </div>
    );
  }

  const {
    content,
    tokens,
    citations,
    confidence,
    isStreaming,
    isThinking = false,
  } = props;

  const hasLowConfidence =
    confidence !== null && confidence < LOW_CONFIDENCE_THRESHOLD;

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] flex flex-col gap-2">
        <motion.div
          initial={{ opacity: 0, y: 6, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.2 }}
          className="bg-white border border-zinc-200 rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm text-zinc-800 shadow-sm"
        >
          {isThinking ? (
            <ThinkingIndicator />
          ) : isStreaming || tokens.length > 0 ? (
            <StreamingText tokens={tokens} isStreaming={isStreaming} />
          ) : (
            <span className="whitespace-pre-wrap break-words">{content}</span>
          )}
        </motion.div>

        {hasLowConfidence && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-1.5 text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-lg px-2.5 py-1"
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
              visible: { transition: { staggerChildren: 0.06 } },
            }}
          >
            {citations.map((c, i) => (
              <motion.div
                key={i}
                variants={{
                  hidden: { opacity: 0, y: 4 },
                  visible: { opacity: 1, y: 0 },
                }}
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
