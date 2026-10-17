'use client';

import { useRef } from 'react';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import type { FeedbackImageError } from '@/lib/hooks/useFeedbackImage';

interface FeedbackImagePickerProps {
  previewUrl: string | null;
  uploading: boolean;
  error: FeedbackImageError;
  onPick: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
}

export function FeedbackImagePicker({ previewUrl, uploading, error, onPick, onClear, disabled }: FeedbackImagePickerProps) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-col gap-1.5">
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="sr-only"
        aria-label={t('feedback.image.attach')}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPick(file);
          e.target.value = '';
        }}
      />
      {previewUrl ? (
        <div className="flex items-center gap-3 rounded-xl border border-zinc-200 p-2 dark:border-white/10">
          {/* eslint-disable-next-line @next/next/no-img-element -- blob: preview, next/image can't optimise it */}
          <img src={previewUrl} alt={t('feedback.image.preview_alt')} className="h-14 w-14 rounded-lg object-cover" />
          <span className="flex-1 text-xs text-zinc-500 dark:text-zinc-400" role="status">
            {uploading ? t('feedback.image.uploading') : t('feedback.image.ready')}
          </span>
          <Button type="button" variant="ghost" size="sm" onClick={onClear} disabled={uploading}>
            {t('feedback.image.remove')}
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="self-start"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
            <path d="M11.5 1A3.5 3.5 0 0 1 15 4.5v7a3.5 3.5 0 0 1-3.5 3.5h-7A3.5 3.5 0 0 1 1 11.5v-7A3.5 3.5 0 0 1 4.5 1h7ZM3 11.69V11.5l2.2-2.2a1 1 0 0 1 1.4 0l1.1 1.1 2.2-2.7a1 1 0 0 1 1.55 0L13 10.1v1.4A1.5 1.5 0 0 1 11.5 13h-7c-.64 0-1.18-.4-1.4-.96-.07-.1-.1-.23-.1-.35ZM5.5 4a1.25 1.25 0 1 0 0 2.5 1.25 1.25 0 0 0 0-2.5Z" />
          </svg>
          {t('feedback.image.attach')}
        </Button>
      )}
      <p className="text-[11px] text-zinc-400 dark:text-zinc-500">{t('feedback.image.hint')}</p>
      {error && (
        <p className="text-xs font-medium text-red-600 dark:text-red-400" role="alert">
          {t(`feedback.image.error.${error}`)}
        </p>
      )}
    </div>
  );
}
