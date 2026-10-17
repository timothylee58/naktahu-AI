'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { FeedbackImagePicker } from '@/components/feedback/FeedbackImagePicker';
import { useFeedbackImage } from '@/lib/hooks/useFeedbackImage';

interface WrongAnswerPanelProps {
  canAttach: boolean;
  submitting: boolean;
  onSubmit: (details: { comment: string; attachmentPath: string | null }) => void;
  onCancel: () => void;
}

// Shown after 👎. Attachments need an account (the upload endpoint is
// authenticated), so anonymous users only get the comment box.
export function WrongAnswerPanel({ canAttach, submitting, onSubmit, onCancel }: WrongAnswerPanelProps) {
  const { t } = useI18n();
  const [comment, setComment] = useState('');
  const image = useFeedbackImage();

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-2 flex w-full max-w-md flex-col gap-2 rounded-2xl border border-zinc-200 bg-white p-3 shadow-sm dark:border-white/10 dark:bg-white/5"
      role="group"
      aria-label={t('chat.wrong.title')}
    >
      <p className="text-xs font-semibold">{t('chat.wrong.title')}</p>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        maxLength={500}
        rows={2}
        aria-label={t('chat.wrong.placeholder')}
        placeholder={t('chat.wrong.placeholder')}
        className="rounded-xl border border-zinc-200 bg-transparent p-2 text-sm focus:border-nk-official/50 focus:outline-none dark:border-white/10 dark:placeholder:text-zinc-500"
      />
      {canAttach ? (
        <FeedbackImagePicker
          previewUrl={image.previewUrl}
          uploading={image.uploading}
          error={image.error}
          onPick={(f) => void image.pick(f)}
          onClear={image.clear}
        />
      ) : (
        <p className="text-[11px] text-zinc-400 dark:text-zinc-500">{t('chat.wrong.sign_in_to_attach')}</p>
      )}
      <div className="flex items-center gap-2">
        <Button
          type="button"
          size="sm"
          disabled={submitting || image.uploading}
          onClick={() => onSubmit({ comment: comment.trim(), attachmentPath: image.attachmentPath })}
        >
          {submitting ? t('profile.feedback.submitting') : t('chat.wrong.send')}
        </Button>
        <Button type="button" size="sm" variant="ghost" disabled={submitting} onClick={onCancel}>
          {t('chat.wrong.cancel')}
        </Button>
      </div>
    </motion.div>
  );
}
