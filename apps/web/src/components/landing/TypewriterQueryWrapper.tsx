'use client';

import { useI18n } from '@/lib/i18n';
import { TypewriterQuery } from './TypewriterQuery';

export function TypewriterQueryWrapper() {
  const { locale } = useI18n();
  return <TypewriterQuery locale={locale} />;
}
