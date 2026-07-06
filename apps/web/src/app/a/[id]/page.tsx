'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { CitationChip } from '@/components/chat/CitationChip';
import type { Citation } from '@/lib/types';

const API_BASE =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : '';

interface SharedAnswer {
  id: string;
  query: string;
  response_text: string;
  citations: Citation[];
  domain: string;
  language: string;
  confidence: number | null;
}

export default function SharedAnswerPage() {
  const { t } = useI18n();
  const params = useParams<{ id: string }>();
  const [answer, setAnswer] = useState<SharedAnswer | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'not-found' | 'error'>('loading');

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/api/v1/share/${params.id}`)
      .then((res) => {
        if (res.status === 404) {
          if (active) setStatus('not-found');
          return null;
        }
        if (!res.ok) throw new Error('fetch failed');
        return res.json() as Promise<SharedAnswer>;
      })
      .then((data) => {
        if (!active || !data) return;
        setAnswer(data);
        setStatus('ready');
      })
      .catch(() => {
        if (active) setStatus('error');
      });
    return () => {
      active = false;
    };
  }, [params.id]);

  return (
    <div className="min-h-screen bg-zinc-50/50 flex flex-col">
      <header className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 bg-white/90 backdrop-blur-md sticky top-0 z-10 shadow-sm">
        <Link href="/" className="flex flex-col">
          <span className="text-base font-bold text-zinc-900 tracking-tight">
            {t('header.title')}
          </span>
          <span className="text-xs text-zinc-500">{t('header.subtitle')}</span>
        </Link>
        <Link
          href="/chat"
          className="text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded-full px-4 py-2 transition-colors shadow-sm"
        >
          {t('share.cta')}
        </Link>
      </header>

      <main className="flex-1 max-w-2xl w-full mx-auto px-4 py-10">
        {status === 'loading' && (
          <div className="flex flex-col gap-3 animate-pulse">
            <div className="h-5 w-2/3 bg-zinc-200 rounded" />
            <div className="h-24 bg-zinc-100 rounded-2xl" />
          </div>
        )}

        {status === 'not-found' && (
          <div className="text-center py-16">
            <p className="text-zinc-500">{t('share.not_found')}</p>
            <Link href="/chat" className="mt-4 inline-block text-sm font-semibold text-blue-600 hover:text-blue-500">
              {t('share.cta')}
            </Link>
          </div>
        )}

        {status === 'error' && (
          <div className="text-center py-16">
            <p className="text-zinc-500">{t('pricing.error')}</p>
          </div>
        )}

        {status === 'ready' && answer && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="flex flex-col gap-4"
          >
            <div className="flex justify-end">
              <div className="max-w-[85%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed shadow-sm">
                {answer.query}
              </div>
            </div>

            <div className="flex justify-start gap-2.5">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center mt-1 shadow-sm">
                <span className="text-white text-[10px] font-bold">AI</span>
              </div>
              <div className="max-w-[85%] flex flex-col gap-2">
                <div className="bg-white border border-zinc-100 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-zinc-800 shadow-sm ring-1 ring-zinc-900/5">
                  <span className="chat-content text-sm leading-relaxed">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer.response_text}</ReactMarkdown>
                  </span>
                </div>

                {answer.citations.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {answer.citations.map((c, i) => (
                      <CitationChip key={i} citation={c} />
                    ))}
                  </div>
                )}
              </div>
            </div>

            <p className="text-xs text-zinc-400 text-center mt-4">{t('share.disclaimer')}</p>
          </motion.div>
        )}
      </main>
    </div>
  );
}
