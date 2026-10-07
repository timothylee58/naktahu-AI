'use client';

import { useCallback, useRef, useState } from 'react';
import { useI18n } from '@/lib/i18n';
import { API_BASE } from '@/lib/api-base';

type TargetLanguage = 'bm' | 'en' | 'zh';

const LANG_LABELS: Record<TargetLanguage, string> = { bm: 'BM', en: 'EN', zh: '中文' };
const LANGUAGES: TargetLanguage[] = ['en', 'bm', 'zh'];

interface TranslateControlProps {
  content: string;
  /** Called with the translated text, or null to revert to the original. */
  onTranslated: (text: string | null, language: TargetLanguage | null) => void;
  /** The language currently being displayed (null = original), so re-clicking
   * the active language toggles back rather than re-requesting the same text. */
  activeLanguage: TargetLanguage | null;
  accessToken?: string;
}

export function TranslateControl({ content, onTranslated, activeLanguage, accessToken }: TranslateControlProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState<TargetLanguage | null>(null);
  const [error, setError] = useState(false);
  // Per-language cache so switching between EN/BM/ZH on the same answer
  // (or reverting then re-picking one already seen) never re-requests —
  // one answer's translations are stable, no reason to burn a second call.
  const cache = useRef<Partial<Record<TargetLanguage, string>>>({});

  const handlePick = useCallback(
    async (lang: TargetLanguage) => {
      setOpen(false);
      if (activeLanguage === lang) {
        onTranslated(null, null); // toggle off — back to original
        return;
      }
      const cached = cache.current[lang];
      if (cached) {
        onTranslated(cached, lang);
        return;
      }
      setLoading(lang);
      setError(false);
      try {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;
        const res = await fetch(`${API_BASE}/api/v1/translate`, {
          method: 'POST',
          headers,
          body: JSON.stringify({ text: content, target_language: lang }),
        });
        if (!res.ok) throw new Error('translate-failed');
        const data = (await res.json()) as { translated_text: string };
        cache.current[lang] = data.translated_text;
        onTranslated(data.translated_text, lang);
      } catch {
        setError(true);
        setTimeout(() => setError(false), 2500);
      } finally {
        setLoading(null);
      }
    },
    [activeLanguage, content, onTranslated, accessToken],
  );

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title={t('chat.actions.translate')}
        className={`p-1.5 rounded-lg transition-colors ${
          activeLanguage
            ? 'text-nk-official bg-nk-official/10'
            : error
              ? 'text-red-500'
              : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 dark:text-zinc-500 dark:hover:text-zinc-200 dark:hover:bg-white/10'
        }`}
      >
        {loading ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="none" className="w-3.5 h-3.5 animate-spin">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.25" />
            <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
            <path fillRule="evenodd" d="M8.75 2.75a.75.75 0 0 0-1.5 0v.5h-2.5a.75.75 0 0 0 0 1.5h.163a8.605 8.605 0 0 0 1.61 3.6 8.638 8.638 0 0 1-2.011 1.276.75.75 0 0 0 .576 1.385 10.13 10.13 0 0 0 2.32-1.517 9.87 9.87 0 0 0 1.06 1.008.75.75 0 1 0 .942-1.167 8.386 8.386 0 0 1-.998-.953 8.605 8.605 0 0 0 1.535-3.632h.164a.75.75 0 0 0 0-1.5H8.75v-.5ZM5.734 4.75h4.032a7.11 7.11 0 0 1-1.229 2.601 7.106 7.106 0 0 1-1.767-2.601h-1.036Zm7.256 4.5a.75.75 0 0 1 .692.462l2.25 5.5a.75.75 0 1 1-1.388.567l-.474-1.158h-2.912l-.475 1.158a.75.75 0 1 1-1.388-.567l2.25-5.5a.75.75 0 0 1 .692-.462h.753Zm-.376 1.777-.921 2.25h1.842l-.921-2.25Z" clipRule="evenodd" />
          </svg>
        )}
      </button>

      {open && (
        <>
          {/* Click-away backdrop */}
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 mb-1 z-20 flex flex-col gap-0.5 bg-white border border-zinc-200 rounded-xl shadow-lg p-1 dark:bg-[#141929] dark:border-white/10 min-w-[88px]">
            {LANGUAGES.map((lang) => (
              <button
                key={lang}
                type="button"
                onClick={() => void handlePick(lang)}
                className={`flex items-center justify-between gap-2 text-xs font-medium rounded-lg px-2.5 py-1.5 transition-colors ${
                  activeLanguage === lang
                    ? 'text-nk-official bg-nk-official/10'
                    : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-white/10'
                }`}
              >
                {LANG_LABELS[lang]}
                {activeLanguage === lang && (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3 h-3">
                    <path fillRule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
