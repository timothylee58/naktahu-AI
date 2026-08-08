'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useI18n } from '@/lib/i18n';
import { suggestForQuery } from '@/lib/agent-suggestions';

interface SuggestionTeaserProps {
  variant?: 'light' | 'dark';
}

/** Condensed "Suggested for you" teaser shown in the persistent sidebar
 * (see AppSidebar) — same rule-based engine as the full experience on
 * /profile, just showing the single top match with a link to see more
 * there. Kept intentionally small: this is a teaser, not a duplicate of
 * the full page. */
export function SuggestionTeaser({ variant = 'light' }: SuggestionTeaserProps) {
  const { t } = useI18n();
  const isDark = variant === 'dark';
  const [query, setQuery] = useState('');
  const top = query.trim() ? suggestForQuery(query)[0] : null;

  return (
    <div
      className={`mx-2 mb-3 rounded-xl border p-3 flex flex-col gap-2 ${
        isDark ? 'border-white/10 bg-white/5' : 'border-blue-200 bg-blue-50/80'
      }`}
    >
      <span
        className={`text-[11px] font-semibold uppercase tracking-wider px-1 locale-nowrap ${
          isDark ? 'text-blue-300' : 'text-blue-800'
        }`}
      >
        {t('profile.suggestions_title')}
      </span>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('suggestions.teaser_placeholder')}
        className={`text-xs rounded-lg px-2.5 py-1.5 border bg-transparent focus:outline-none ${
          isDark ? 'border-white/10 placeholder:text-zinc-500 text-zinc-200' : 'border-blue-200 placeholder:text-zinc-400 text-zinc-800'
        }`}
      />
      {top && (
        <Link
          href={top.kind === 'agent' ? top.href : top.docsHref}
          className={`text-xs font-medium ${isDark ? 'text-blue-300 hover:text-blue-200' : 'text-blue-700 hover:text-blue-800'}`}
        >
          {top.kind === 'agent' ? t(top.titleKey) : `${top.method} ${top.endpoint}`} →
        </Link>
      )}
      <Link
        href="/profile"
        className={`text-[11px] ${isDark ? 'text-zinc-500 hover:text-zinc-300' : 'text-zinc-400 hover:text-zinc-600'}`}
      >
        {t('suggestions.teaser_see_more')}
      </Link>
    </div>
  );
}
