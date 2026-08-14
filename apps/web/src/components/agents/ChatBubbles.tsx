'use client';

import { cn } from '@/lib/utils';

export interface ChatMessage {
  id: string;
  role: 'user' | 'bot';
  content: string;
}

interface ChatBubblesProps {
  messages: ChatMessage[];
  className?: string;
}

export function ChatBubbles({ messages, className }: ChatBubblesProps) {
  if (messages.length === 0) return null;

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={cn(
            'flex',
            msg.role === 'user' ? 'justify-end' : 'justify-start',
          )}
        >
          <div
            className={cn(
              'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
              msg.role === 'user'
                ? 'rounded-br-md bg-nk-official text-white'
                : 'rounded-bl-md border border-zinc-200 bg-zinc-50 text-zinc-800',
            )}
          >
            {msg.role === 'bot' && (
              <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                NakTahu
              </span>
            )}
            <p className="whitespace-pre-wrap">{msg.content}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

interface QuickRepliesProps {
  options: string[];
  onSelect: (option: string) => void;
  className?: string;
}

export function QuickReplies({ options, onSelect, className }: QuickRepliesProps) {
  if (options.length === 0) return null;

  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onSelect(opt)}
          className="rounded-full border border-nk-official/30 bg-nk-official/10 px-3 py-1.5 text-xs font-medium text-nk-official-dim transition-colors hover:bg-nk-official/20 dark:border-nk-official/30 dark:bg-nk-official/10 dark:text-nk-official"
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
