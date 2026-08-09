'use client';

import Link from 'next/link';
import { useI18n } from '@/lib/i18n';
import type { Suggestion } from '@/lib/agent-suggestions';

interface SuggestionCardProps {
  suggestion: Suggestion;
  /** Passed by AuthButton's popover to close it on click, since a plain
   * <Link> navigation alone doesn't unmount the popover — leaving the
   * full-viewport dismiss overlay behind after client-side routing
   * (confirmed Bugbot finding). /profile has no popover to close, so it
   * omits this. */
  onNavigate?: () => void;
}

/** Shared rendering for one agent-suggestions.ts result — used by both the
 * full /profile page and the condensed profile-button popover in
 * AppSidebar, so the two never drift in how a suggestion is presented. */
export function SuggestionCard({ suggestion, onNavigate }: SuggestionCardProps) {
  const { t } = useI18n();
  if (suggestion.kind === 'agent') {
    return (
      <Link
        href={suggestion.href}
        onClick={onNavigate}
        className="flex flex-col gap-1 rounded-xl border border-zinc-200 p-3 transition-colors hover:border-blue-400 hover:bg-blue-50 dark:border-white/10 dark:hover:bg-blue-500/10"
      >
        <span className="text-[10px] font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-400">
          {t('suggestions.agent_badge')}
        </span>
        <span className="text-sm font-semibold">{t(suggestion.titleKey)}</span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400 line-clamp-2">{t(suggestion.descKey)}</span>
      </Link>
    );
  }
  return (
    <Link
      href={suggestion.docsHref}
      onClick={onNavigate}
      className="flex flex-col gap-1 rounded-xl border border-zinc-200 p-3 transition-colors hover:border-emerald-400 hover:bg-emerald-50 dark:border-white/10 dark:hover:bg-emerald-500/10"
    >
      <span className="text-[10px] font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
        {t('suggestions.api_badge')}
      </span>
      <span className="text-sm font-mono font-semibold">{suggestion.method} {suggestion.endpoint}</span>
      <span className="text-xs text-zinc-500 dark:text-zinc-400">{t(suggestion.labelKey)}</span>
    </Link>
  );
}
