'use client';

import { useEffect, useState } from 'react';
import { useI18n } from '@/lib/i18n';
import { useAgentApi } from '@/lib/hooks/useAgentApi';

// Replaces the mailto: placeholder profile/page.tsx used to point at — see
// that file's git history and 047_product_feedback.sql's docstring for why
// a dedicated table/endpoint was needed instead of reusing the per-answer
// thumbs rating in routers/feedback.py. Scoped explicitly against that
// per-answer 👍/👎 in chat (ResponseActions.tsx) — that channel already
// captures the query/citations/domain automatically; this one is for
// everything that isn't about one specific answer: bugs, feature requests,
// general product feedback.

interface FeedbackEntry {
  id: string;
  category: 'bug' | 'feature_request' | 'general';
  title: string;
  status: string;
  created_at: string;
}

type SubmitStatus = { kind: 'idle' } | { kind: 'success' } | { kind: 'error' };

const CATEGORIES = ['bug', 'feature_request', 'general'] as const;

const STATUS_STYLE: Record<string, string> = {
  new: 'text-zinc-500 dark:text-zinc-400',
  reviewing: 'text-amber-600 dark:text-amber-400',
  planned: 'text-nk-official-dim dark:text-nk-official',
  done: 'text-green-600 dark:text-green-400',
  declined: 'text-zinc-400 dark:text-zinc-500',
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function ProductFeedbackCard() {
  const { t } = useI18n();
  const { post, get } = useAgentApi();
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>('bug');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<SubmitStatus>({ kind: 'idle' });
  const [entries, setEntries] = useState<FeedbackEntry[]>([]);
  const [loadedOnce, setLoadedOnce] = useState(false);

  const loadEntries = () => {
    void get('/api/v1/product-feedback')
      .then((res) => setEntries((res.results as FeedbackEntry[]) ?? []))
      .catch(() => {
        /* best-effort — the form still works without the history list */
      })
      .finally(() => setLoadedOnce(true));
  };

  useEffect(() => {
    loadEntries();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    if (!title.trim() || !description.trim()) return;
    setLoading(true);
    setStatus({ kind: 'idle' });
    try {
      await post('/api/v1/product-feedback', {
        category,
        title: title.trim(),
        description: description.trim(),
        page_context: typeof window !== 'undefined' ? window.location.pathname : undefined,
      });
      setStatus({ kind: 'success' });
      setTitle('');
      setDescription('');
      loadEntries();
    } catch {
      setStatus({ kind: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="bg-white rounded-2xl border border-zinc-200 p-5 flex flex-col gap-3 shadow-sm dark:bg-white/5 dark:border-white/10">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
        {t('profile.feedback.title')}
      </span>
      <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('profile.feedback.desc')}</p>
      <p className="text-xs text-zinc-400 dark:text-zinc-500">{t('profile.feedback.scope_note')}</p>

      <div className="flex gap-1.5">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setCategory(c)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
              category === c
                ? 'bg-nk-official text-white'
                : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-white/10 dark:text-zinc-300 dark:hover:bg-white/15'
            }`}
          >
            {t(`profile.feedback.category.${c}`)}
          </button>
        ))}
      </div>

      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={150}
        placeholder={t('profile.feedback.title_placeholder')}
        className="border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-nk-official/50 dark:border-white/10 dark:placeholder:text-zinc-500"
      />
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        maxLength={2000}
        rows={3}
        placeholder={t('profile.feedback.description_placeholder')}
        className="border border-zinc-200 rounded-xl p-2.5 text-sm bg-transparent focus:outline-none focus:border-nk-official/50 dark:border-white/10 dark:placeholder:text-zinc-500"
      />

      <button
        type="button"
        disabled={loading || !title.trim() || !description.trim()}
        onClick={() => void submit()}
        className="self-start px-4 py-2 bg-nk-official/10 hover:bg-nk-official/20 text-nk-official-dim dark:text-nk-official rounded-full text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? t('profile.feedback.submitting') : t('profile.feedback.button')}
      </button>

      {status.kind === 'success' && (
        <p className="text-xs font-medium text-green-600 dark:text-green-400">{t('profile.feedback.success')}</p>
      )}
      {status.kind === 'error' && (
        <p className="text-xs font-medium text-red-600 dark:text-red-400">{t('profile.feedback.error')}</p>
      )}

      {loadedOnce && entries.length > 0 && (
        <div className="flex flex-col gap-1.5 mt-1 pt-3 border-t border-zinc-100 dark:border-white/10">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
            {t('profile.feedback.yours')}
          </p>
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between gap-2">
              <span className="text-xs text-zinc-600 dark:text-zinc-300 truncate">{entry.title}</span>
              <span className={`text-[10px] font-semibold uppercase flex-shrink-0 ${STATUS_STYLE[entry.status] ?? STATUS_STYLE.new}`}>
                {t(`profile.feedback.status.${entry.status}`) === `profile.feedback.status.${entry.status}`
                  ? entry.status
                  : t(`profile.feedback.status.${entry.status}`)}
              </span>
              <span className="text-[10px] text-zinc-400 dark:text-zinc-500 flex-shrink-0">{formatDate(entry.created_at)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
