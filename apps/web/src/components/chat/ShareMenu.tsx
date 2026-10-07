'use client';

import { useCallback, useRef, useState } from 'react';
import { useI18n } from '@/lib/i18n';
import { API_BASE } from '@/lib/api-base';
import type { Citation } from '@/lib/types';

// Real share targets (WhatsApp/Telegram/Facebook deep links) plus an
// optional AI-drafted caption — "make sharing effortless" per this
// product's actual distribution channel (Malaysian civic questions get
// forwarded in WhatsApp groups/Telegram/FB far more than they get typed
// into Google). This never posts anything on the user's behalf: every
// target here is a plain client-side navigation to the platform's own
// public share URL (wa.me, t.me, facebook.com/sharer) that opens THEIR
// share composer for a human to review and send — same "no automation of
// real-world posting" boundary already established for WhatsApp escalation
// elsewhere in this app (PropertyLah's wa.me-only decision).

interface ShareMenuProps {
  content: string;
  query?: string;
  domain?: string;
  language?: string;
  citations?: Citation[];
  confidence?: number | null;
  accessToken?: string;
}

type LinkState = { status: 'idle' } | { status: 'creating' } | { status: 'ready'; url: string } | { status: 'error' };
type CaptionState = { status: 'idle' } | { status: 'drafting' } | { status: 'ready'; text: string } | { status: 'error' };

export function ShareMenu({ content, query, domain, language, citations, confidence, accessToken }: ShareMenuProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [linkState, setLinkState] = useState<LinkState>({ status: 'idle' });
  const [captionState, setCaptionState] = useState<CaptionState>({ status: 'idle' });
  const [justCopiedLink, setJustCopiedLink] = useState(false);
  const [justCopiedCaption, setJustCopiedCaption] = useState(false);
  // Memoises the in-flight/completed permalink creation so every share
  // target (copy/WhatsApp/Telegram/Facebook) reuses the same link instead
  // of minting a new shared_answers row per click.
  const linkPromiseRef = useRef<Promise<string> | null>(null);

  const authHeaders = useCallback((): Record<string, string> => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
    return headers;
  }, [accessToken]);

  const ensureShareLink = useCallback(async (): Promise<string> => {
    if (linkPromiseRef.current) return linkPromiseRef.current;
    const promise = (async () => {
      setLinkState({ status: 'creating' });
      const res = await fetch(`${API_BASE}/api/v1/share`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          query,
          response_text: content,
          citations: citations ?? [],
          domain: domain ?? 'general',
          language: language ?? 'en',
          confidence: confidence ?? null,
        }),
      });
      if (!res.ok) throw new Error('share_link_failed');
      const data = (await res.json()) as { id: string };
      const url = `${window.location.origin}/a/${data.id}`;
      setLinkState({ status: 'ready', url });
      return url;
    })().catch((err) => {
      setLinkState({ status: 'error' });
      linkPromiseRef.current = null; // allow retry on the next click
      throw err;
    });
    linkPromiseRef.current = promise;
    return promise;
  }, [query, content, citations, domain, language, confidence, authHeaders]);

  const handleCopyLink = useCallback(async () => {
    try {
      const url = await ensureShareLink();
      await navigator.clipboard.writeText(url);
      setJustCopiedLink(true);
      setTimeout(() => setJustCopiedLink(false), 2000);
    } catch {
      // linkState already reflects the error
    }
  }, [ensureShareLink]);

  const openShareTarget = useCallback(
    async (build: (url: string, caption: string) => string) => {
      try {
        const url = await ensureShareLink();
        const caption = captionState.status === 'ready' ? captionState.text : '';
        window.open(build(url, caption), '_blank', 'noopener,noreferrer');
      } catch {
        // linkState already reflects the error; nothing to open
      }
    },
    [ensureShareLink, captionState],
  );

  const handleDraftCaption = useCallback(async () => {
    if (!query || captionState.status === 'drafting') return;
    setCaptionState({ status: 'drafting' });
    try {
      const res = await fetch(`${API_BASE}/api/v1/share/caption`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ query, answer: content, language: language ?? 'en' }),
      });
      if (!res.ok) throw new Error('caption_failed');
      const data = (await res.json()) as { caption: string };
      setCaptionState({ status: 'ready', text: data.caption });
    } catch {
      setCaptionState({ status: 'error' });
    }
  }, [query, content, language, authHeaders, captionState.status]);

  const handleCopyCaption = useCallback(async () => {
    if (captionState.status !== 'ready') return;
    await navigator.clipboard.writeText(captionState.text);
    setJustCopiedCaption(true);
    setTimeout(() => setJustCopiedCaption(false), 2000);
  }, [captionState]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title={t('chat.actions.share')}
        className={`p-1.5 rounded-lg transition-colors ${
          linkState.status === 'error'
            ? 'text-red-500'
            : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 dark:text-zinc-500 dark:hover:text-zinc-200 dark:hover:bg-white/10'
        }`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
          <path d="M11.5 2a2.5 2.5 0 1 0-2.457 2.964l-3.5 2.121a2.5 2.5 0 1 0 0 3.83l3.5 2.121a2.5 2.5 0 1 0 .757-1.279l-3.5-2.121a2.51 2.51 0 0 0 0-1.272l3.5-2.121A2.5 2.5 0 0 0 11.5 2Z" />
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 mb-1 z-20 flex flex-col gap-0.5 bg-white border border-zinc-200 rounded-xl shadow-lg p-1.5 dark:bg-[#141929] dark:border-white/10 w-64">
            <button
              type="button"
              onClick={() => void handleCopyLink()}
              className="flex items-center justify-between gap-2 text-xs font-medium rounded-lg px-2.5 py-1.5 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/10 text-left"
            >
              {justCopiedLink ? t('chat.actions.share_copied') : t('chat.share_menu.copy_link')}
            </button>
            <button
              type="button"
              onClick={() => void openShareTarget((url, caption) => `https://wa.me/?text=${encodeURIComponent(caption ? `${caption}\n${url}` : url)}`)}
              className="flex items-center gap-2 text-xs font-medium rounded-lg px-2.5 py-1.5 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/10 text-left"
            >
              {t('chat.share_menu.whatsapp')}
            </button>
            <button
              type="button"
              onClick={() => void openShareTarget((url, caption) => `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(caption)}`)}
              className="flex items-center gap-2 text-xs font-medium rounded-lg px-2.5 py-1.5 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/10 text-left"
            >
              {t('chat.share_menu.telegram')}
            </button>
            <button
              type="button"
              onClick={() => void openShareTarget((url, caption) => `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}&quote=${encodeURIComponent(caption)}`)}
              className="flex items-center gap-2 text-xs font-medium rounded-lg px-2.5 py-1.5 text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/10 text-left"
            >
              {t('chat.share_menu.facebook')}
            </button>

            <div className="my-1 border-t border-zinc-100 dark:border-white/10" />

            {captionState.status === 'ready' ? (
              <div className="flex flex-col gap-1.5 px-1 py-1">
                <p className="text-[11px] leading-snug text-zinc-600 dark:text-zinc-300 bg-zinc-50 dark:bg-white/5 rounded-lg p-2">
                  {captionState.text}
                </p>
                <button
                  type="button"
                  onClick={() => void handleCopyCaption()}
                  className="self-start text-[11px] font-semibold text-nk-official-dim dark:text-nk-official"
                >
                  {justCopiedCaption ? t('chat.actions.share_copied') : t('chat.share_menu.copy_caption')}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => void handleDraftCaption()}
                disabled={captionState.status === 'drafting' || !query}
                className="flex items-center gap-2 text-xs font-medium rounded-lg px-2.5 py-1.5 text-nk-official-dim dark:text-nk-official hover:bg-zinc-100 dark:hover:bg-white/10 text-left disabled:opacity-50"
              >
                {captionState.status === 'drafting'
                  ? t('chat.share_menu.drafting')
                  : captionState.status === 'error'
                    ? t('chat.share_menu.draft_error_retry')
                    : t('chat.share_menu.draft_caption')}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
