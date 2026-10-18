'use client';

import { TriangleAlert } from 'lucide-react';
import { useI18n } from '@/lib/i18n';

export function PiiWarning({ onRemove }: { onRemove: () => void }) {
  const { t } = useI18n();
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl bg-[var(--nk-warn-bg)] px-3.5 py-3 text-left text-[13px] leading-normal text-nk-ink"
    >
      <TriangleAlert aria-hidden className="mt-px h-[18px] w-[18px] shrink-0 text-nk-community" />
      <div className="flex flex-col gap-1">
        <span>
          {t('pii.warn')}{' '}
          <button
            type="button"
            onClick={onRemove}
            className="font-semibold text-nk-community-text-warn underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-nk-official"
          >
            {t('pii.remove')}
          </button>
        </span>
        <span className="text-nk-muted-aa">{t('pii.confirm_hint')}</span>
      </div>
    </div>
  );
}
