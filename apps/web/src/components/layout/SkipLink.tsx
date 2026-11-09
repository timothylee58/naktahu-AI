'use client';

import type { MouseEvent } from 'react';
import { useI18n } from '@/lib/i18n';

// First focusable element on every page. Visually hidden until focused, then
// jumps past the header/nav. Pages mark their content with id="main-content";
// pages that only have a <main> still work via the fallback, so the link is
// never a dead anchor on a page that forgot the id.
export function SkipLink() {
  const { t } = useI18n();

  const skip = (e: MouseEvent<HTMLAnchorElement>) => {
    const target = document.getElementById('main-content') ?? document.querySelector('main');
    if (!target) return;
    e.preventDefault();
    if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
    target.focus();
    target.scrollIntoView({ block: 'start' });
  };

  return (
    <a
      href="#main-content"
      onClick={skip}
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-nk-official focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-white"
    >
      {t('a11y.skip_to_main')}
    </a>
  );
}
