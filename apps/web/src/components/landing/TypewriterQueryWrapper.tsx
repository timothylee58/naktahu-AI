'use client';

import { useI18n } from '@/lib/i18n';
import { TypewriterQuery } from './TypewriterQuery';

interface TypewriterQueryWrapperProps {
  isDark?: boolean;
}

export function TypewriterQueryWrapper({ isDark = true }: TypewriterQueryWrapperProps) {
  const { locale } = useI18n();
  return <TypewriterQuery locale={locale} isDark={isDark} />;
}
