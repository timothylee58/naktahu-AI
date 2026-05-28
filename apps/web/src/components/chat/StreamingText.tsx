'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface StreamingTextProps {
  tokens: string[];
  isStreaming: boolean;
}

export function StreamingText({ tokens, isStreaming }: StreamingTextProps) {
  const text = tokens.join('');

  return (
    <span className="chat-content text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
      {isStreaming && (
        <span
          aria-hidden
          className="inline-block w-0.5 h-[1em] bg-current align-text-bottom ml-px animate-blink"
        />
      )}
    </span>
  );
}
