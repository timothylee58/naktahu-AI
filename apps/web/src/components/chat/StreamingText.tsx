'use client';

import { motion } from 'framer-motion';

interface StreamingTextProps {
  tokens: string[];
  isStreaming: boolean;
}

export function StreamingText({ tokens, isStreaming }: StreamingTextProps) {
  return (
    <span className="whitespace-pre-wrap break-words">
      {tokens.map((token, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.1 }}
        >
          {token}
        </motion.span>
      ))}
      {isStreaming && (
        <span
          aria-hidden
          className="inline-block w-0.5 h-[1em] bg-current align-text-bottom ml-px animate-blink"
        />
      )}
    </span>
  );
}
