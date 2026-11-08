'use client';

import { useI18n } from '@/lib/i18n';

interface MakaKamiBadgeProps {
  className?: string;
}

export function MakaKamiBadge({ className = '' }: MakaKamiBadgeProps) {
  const { t } = useI18n();
  return (
    <a
      href="https://makakami.com.my/app/naktahu-my"
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-block transition-opacity hover:opacity-80 ${className}`}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- external SVG badge; next/image would need remotePatterns for one asset */}
      <img
        src="https://makakami.com.my/badge/naktahu-my.svg"
        alt={t('footer.makakami_alt')}
        width={150}
        height={40}
        loading="lazy"
      />
    </a>
  );
}
