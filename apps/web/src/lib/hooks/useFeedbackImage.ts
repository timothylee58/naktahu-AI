'use client';

import { useCallback, useEffect, useState } from 'react';
import { useAgentApi } from '@/lib/hooks/useAgentApi';

export const FEEDBACK_IMAGE_MAX_BYTES = 3 * 1024 * 1024;
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

export type FeedbackImageError = 'type' | 'size' | 'upload' | null;

// Uploads on pick (not on submit) so the verifier's verdict on the image shows
// up while the user is still on the form. The returned path is only a pointer
// into a private bucket; the server re-checks it belongs to the caller.
export function useFeedbackImage() {
  const { upload } = useAgentApi();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [attachmentPath, setAttachmentPath] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<FeedbackImageError>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const clear = useCallback(() => {
    setPreviewUrl(null);
    setAttachmentPath(null);
    setError(null);
  }, []);

  const pick = useCallback(
    async (file: File) => {
      setError(null);
      if (!ACCEPTED_TYPES.includes(file.type)) return setError('type');
      if (file.size > FEEDBACK_IMAGE_MAX_BYTES) return setError('size');
      setPreviewUrl(URL.createObjectURL(file));
      setAttachmentPath(null);
      setUploading(true);
      try {
        const form = new FormData();
        form.append('file', file);
        const res = await upload('/api/v1/feedback-attachments', form);
        setAttachmentPath(String(res.attachment_path));
      } catch {
        setPreviewUrl(null);
        setError('upload');
      } finally {
        setUploading(false);
      }
    },
    [upload],
  );

  return { previewUrl, attachmentPath, uploading, error, pick, clear };
}
