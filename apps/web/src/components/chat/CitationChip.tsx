'use client';

import { motion } from 'framer-motion';
import type { Citation } from '@/lib/types';

interface CitationChipProps {
  citation: Citation;
}

function truncate(s: string, max: number) {
  return s.length <= max ? s : `${s.slice(0, max)}…`;
}

export function CitationChip({ citation }: CitationChipProps) {
  const url = citation.url ?? citation.source_url;
  const title = citation.title ?? citation.source_title ?? '';
  const hasUrl = Boolean(url);
  return (
    <motion.a
      href={url}
      target={hasUrl ? '_blank' : undefined}
      rel={hasUrl ? 'noopener noreferrer' : undefined}
      whileHover={hasUrl ? { scale: 1.03 } : undefined}
      transition={{ type: 'spring', stiffness: 400, damping: 20 }}
      className={`inline-flex items-center gap-1.5 bg-blue-50 border border-blue-200 text-blue-800 rounded-full px-3 py-1 text-xs font-medium no-underline transition-colors dark:bg-blue-500/10 dark:border-blue-500/30 dark:text-blue-300 ${hasUrl ? 'cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-500/20' : 'cursor-default'}`}
      title={title}
    >
      <span className="font-semibold truncate max-w-[6rem]">
        {citation.ministry}
      </span>
      <span className="opacity-70">·</span>
      <span className="truncate max-w-[12rem]">
        {truncate(title, 32)}
      </span>
      {hasUrl && (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="w-3 h-3 flex-shrink-0 opacity-60"
          aria-hidden
        >
          <path
            fillRule="evenodd"
            d="M4.5 11.5a.75.75 0 0 0 1.06 0l5-5v2.69a.75.75 0 0 0 1.5 0V5a.75.75 0 0 0-.75-.75H7.06a.75.75 0 0 0 0 1.5H9.75l-5 5a.75.75 0 0 0 0 1.06Z"
            clipRule="evenodd"
          />
        </svg>
      )}
    </motion.a>
  );
}
