'use client';

import Link from 'next/link';
import { ArrowRight, Code2, Languages, Mic, type LucideIcon } from 'lucide-react';
import { useI18n } from '@/lib/i18n';

interface Feature {
  key: 'bilingual' | 'voice' | 'api';
  icon: LucideIcon;
  href?: string;
  ctaKey?: string;
}

// Capabilities the task demos don't show on their own: language coverage,
// speaking instead of typing, and the developer API.
const FEATURES: readonly Feature[] = [
  { key: 'bilingual', icon: Languages },
  { key: 'voice', icon: Mic },
  { key: 'api', icon: Code2, href: '/developer', ctaKey: 'landing.features.api.cta' },
];

export function FeatureStrip() {
  const { t } = useI18n();
  return (
    <ul className="grid gap-4 sm:grid-cols-3 sm:gap-6">
      {FEATURES.map(({ key, icon: Icon, href, ctaKey }) => (
        <li key={key} className="flex flex-col gap-3 rounded-2xl border border-[var(--nk-border)] bg-nk-card p-5 sm:p-6">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--nk-fill-official)] text-nk-official-text">
            <Icon aria-hidden className="h-5 w-5" strokeWidth={1.8} />
          </span>
          <h3 className="font-display text-lg font-bold text-nk-ink">{t(`landing.features.${key}.title`)}</h3>
          <p className="text-base leading-relaxed text-nk-ink/80">{t(`landing.features.${key}.desc`)}</p>
          {href && ctaKey && (
            <Link
              href={href}
              className="mt-auto inline-flex w-fit items-center gap-1 rounded text-sm font-semibold text-nk-official-text underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official"
            >
              {t(ctaKey)}
              <ArrowRight aria-hidden className="h-3.5 w-3.5" />
            </Link>
          )}
        </li>
      ))}
    </ul>
  );
}
