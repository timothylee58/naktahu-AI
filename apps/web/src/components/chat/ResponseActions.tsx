'use client';

import { useCallback, useState } from 'react';
import { motion } from 'framer-motion';
import type { Citation } from '@/lib/types';
import { getAnonSessionId } from '@/lib/anon-session';

const API_BASE =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : '';

interface ResponseActionsProps {
  content: string;
  onRegenerate?: () => void;
  isStreaming: boolean;
  query?: string;
  domain?: string;
  language?: string;
  citations?: Citation[];
  confidence?: number | null;
  accessToken?: string;
}

export function ResponseActions({
  content,
  onRegenerate,
  isStreaming,
  query,
  domain,
  language,
  citations,
  confidence,
  accessToken,
}: ResponseActionsProps) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [shareState, setShareState] = useState<'idle' | 'sharing' | 'copied' | 'error'>('idle');

  const handleCopy = useCallback(async () => {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [content]);

  const handleFeedback = useCallback(
    async (rating: 'up' | 'down') => {
      // Rating is final once submitted — avoids ambiguous null ratings in the dataset.
      if (feedback || submitting || !query) return;
      setFeedback(rating);
      setSubmitting(true);
      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
        const res = await fetch(`${API_BASE}/api/v1/feedback`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            session_id: getAnonSessionId(),
            query,
            response_summary: content.slice(0, 2000),
            citations: citations ?? [],
            domain: domain ?? 'general',
            language: language ?? 'en',
            rating: rating === 'up' ? 1 : -1,
          }),
        });
        if (!res.ok) throw new Error('Failed to submit feedback');
      } catch {
        // Submission failed — revert so the button reflects reality and the user can retry.
        setFeedback(null);
      } finally {
        setSubmitting(false);
      }
    },
    [feedback, submitting, query, content, citations, domain, language, accessToken],
  );

  const handleShare = useCallback(async () => {
    if (!query || shareState === 'sharing') return;
    setShareState('sharing');
    try {
      const res = await fetch(`${API_BASE}/api/v1/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          response_text: content,
          citations: citations ?? [],
          domain: domain ?? 'general',
          language: language ?? 'en',
          confidence: confidence ?? null,
        }),
      });
      if (!res.ok) throw new Error('Failed to create share link');
      const data = (await res.json()) as { id: string };
      await navigator.clipboard.writeText(`${window.location.origin}/a/${data.id}`);
      setShareState('copied');
      setTimeout(() => setShareState('idle'), 2000);
    } catch {
      setShareState('error');
      setTimeout(() => setShareState('idle'), 2000);
    }
  }, [query, content, citations, domain, language, confidence, shareState]);

  if (isStreaming) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: 0.15 }}
      className="flex items-center gap-1 mt-1"
    >
      {/* Copy */}
      <button
        onClick={handleCopy}
        title="Copy"
        className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
      >
        {copied ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5 text-green-500">
            <path fillRule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
            <path fillRule="evenodd" d="M11.986 3H12a2 2 0 0 1 2 2v6a2 2 0 0 1-1.5 1.937V13.5a.5.5 0 0 1-.5.5h-8a.5.5 0 0 1-.5-.5v-9A.5.5 0 0 1 4 4h1.014A2 2 0 0 1 7 3h4.986ZM6 5H4.5v8h7V9.937A2 2 0 0 1 10 8V5H6Zm5-1.5a.5.5 0 0 0-.5-.5H7a.5.5 0 0 0-.5.5V8a.5.5 0 0 0 .5.5h3.5a.5.5 0 0 0 .5-.5V3.5Z" clipRule="evenodd" />
          </svg>
        )}
      </button>

      {/* Share */}
      {query && (
        <button
          onClick={handleShare}
          disabled={shareState === 'sharing'}
          title={
            shareState === 'copied'
              ? 'Link copied'
              : shareState === 'error'
                ? 'Failed to create link'
                : 'Copy shareable link'
          }
          className={`p-1.5 rounded-lg transition-colors disabled:cursor-default ${
            shareState === 'error'
              ? 'text-red-500'
              : shareState === 'copied'
                ? 'text-green-500'
                : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'
          }`}
        >
          {shareState === 'copied' ? (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
              <path fillRule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
              <path d="M11.5 2a2.5 2.5 0 1 0-2.457 2.964l-3.5 2.121a2.5 2.5 0 1 0 0 3.83l3.5 2.121a2.5 2.5 0 1 0 .757-1.279l-3.5-2.121a2.51 2.51 0 0 0 0-1.272l3.5-2.121A2.5 2.5 0 0 0 11.5 2Z" />
            </svg>
          )}
        </button>
      )}

      {/* Regenerate */}
      {onRegenerate && (
        <button
          onClick={onRegenerate}
          title="Regenerate"
          className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
            <path fillRule="evenodd" d="M13.836 2.477a.75.75 0 0 1 .75.75v3.182a.75.75 0 0 1-.75.75h-3.182a.75.75 0 0 1 0-1.5h1.37l-.84-.841a4.5 4.5 0 0 0-7.08.932.75.75 0 0 1-1.3-.75 6 6 0 0 1 9.46-1.242l.842.84V3.227a.75.75 0 0 1 .75-.75Zm-.911 7.5A.75.75 0 0 1 13.199 11a6 6 0 0 1-9.46 1.243l-.842-.84v1.371a.75.75 0 0 1-1.5 0V9.591a.75.75 0 0 1 .75-.75H5.33a.75.75 0 0 1 0 1.5H3.96l.84.841a4.5 4.5 0 0 0 7.08-.932.75.75 0 0 1 1.046-.273Z" clipRule="evenodd" />
          </svg>
        </button>
      )}

      {/* Divider */}
      <div className="w-px h-3 bg-zinc-200 mx-0.5" />

      {/* Thumbs up */}
      <button
        onClick={() => handleFeedback('up')}
        disabled={!!feedback}
        title={feedback ? 'Thanks for the feedback' : 'Helpful'}
        className={`p-1.5 rounded-lg transition-colors ${feedback === 'up' ? 'text-green-600 bg-green-50' : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'} disabled:cursor-default`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
          <path d="M8.864.053a.75.75 0 0 1 .748.712l.003.046c.032.552.063 1.26.063 1.689 0 .766-.152 1.315-.428 1.793-.232.407-.557.78-.882 1.18l-.046.057a10.7 10.7 0 0 0-.734 1.016 5.89 5.89 0 0 0-.558 1.354H2.75a.75.75 0 0 0-.75.75v4c0 .414.336.75.75.75h10.5a.75.75 0 0 0 .75-.75V8.75a.75.75 0 0 0-.75-.75h-1.453l.028-.04c.258-.37.483-.805.653-1.298.156-.455.272-.979.272-1.587 0-.42-.027-1.007-.054-1.5L12.44.765a.75.75 0 0 1 .748-.712h.062c.414 0 .75.336.75.75v4.935A5.25 5.25 0 0 1 8.75 10H2.75A2.25 2.25 0 0 1 .5 7.75V6.25A2.25 2.25 0 0 1 2.75 4h3.557c.087-.416.228-.818.423-1.194.32-.613.76-1.138 1.176-1.63l.034-.04C8.358.688 8.568.43 8.68.18A.75.75 0 0 1 8.864.053Z" />
        </svg>
      </button>

      {/* Thumbs down */}
      <button
        onClick={() => handleFeedback('down')}
        disabled={!!feedback}
        title={feedback ? 'Thanks for the feedback' : 'Not helpful'}
        className={`p-1.5 rounded-lg transition-colors ${feedback === 'down' ? 'text-red-500 bg-red-50' : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'} disabled:cursor-default`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
          <path d="M7.136 15.947a.75.75 0 0 1-.748-.712l-.003-.046c-.032-.552-.063-1.26-.063-1.689 0-.766.152-1.315.428-1.793.232-.407.557-.78.882-1.18l.046-.057c.271-.338.544-.678.734-1.016.19-.337.382-.79.558-1.354H13.25a.75.75 0 0 0 .75-.75v-4a.75.75 0 0 0-.75-.75H2.75a.75.75 0 0 0-.75.75v1.5c0 .414.336.75.75.75h1.453l-.028.04c-.258.37-.483.805-.653 1.298a5.583 5.583 0 0 0-.272 1.587c0 .42.027 1.007.054 1.5l.007.128a.75.75 0 0 1-.748.712h-.062a.75.75 0 0 1-.75-.75V5.315A5.25 5.25 0 0 1 7.25 6h6a2.25 2.25 0 0 1 2.25 2.25v1.5A2.25 2.25 0 0 1 13.25 12H9.693a7.22 7.22 0 0 1-.423 1.194c-.32.613-.76 1.138-1.176 1.63l-.034.04c-.41.448-.62.706-.732.956a.75.75 0 0 1-.184.127Z" />
        </svg>
      </button>
    </motion.div>
  );
}
