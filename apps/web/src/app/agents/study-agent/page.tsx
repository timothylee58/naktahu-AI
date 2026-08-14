'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import Link from 'next/link';
import useSWR from 'swr';
import { useAgentApi } from '@/lib/hooks/useAgentApi';
import { useSupabaseSession } from '@/lib/hooks/useSupabaseSession';
import { AgentPageHeader } from '@/components/agents/AgentPageHeader';
import { useI18n } from '@/lib/i18n';
import { agentTitleKey } from '@/lib/agents';
import {
  agentRunsForAgentKey,
  fetchAgentRunsAuthed,
  HISTORY_SWR_OPTIONS,
  type AgentRunEntry,
} from '@/lib/history';

type Level = 'spm' | 'stpm' | 'a-level';
type Mode = 'explain' | 'quiz';
type InputTab = 'paste' | 'pdf' | 'photo';

const LEVEL_SUBJECTS: Record<Level, string[]> = {
  spm: ['sejarah', 'matematik', 'sains', 'bm', 'bi'],
  stpm: ['matematik_t', 'ekonomi', 'perakaunan', 'sejarah', 'biologi'],
  'a-level': ['mathematics', 'physics', 'chemistry', 'economics', 'biology'],
};

interface QuizItem {
  question_index: number;
  question: string;
  citations?: Array<Record<string, unknown>>;
  student_answer: string | null;
  verdict: { correct?: boolean; partial?: boolean; feedback?: string } | null;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result);
      // strip the "data:<mime>;base64," prefix — backend/API expects raw base64
      resolve(result.slice(result.indexOf(',') + 1));
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function fmt(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), template);
}

function StudyAgentPageInner() {
  const { t } = useI18n();
  const { start, continue: cont, get } = useAgentApi();
  const { supabase, userId } = useSupabaseSession();
  const searchParams = useSearchParams();

  const [level, setLevel] = useState<Level>('spm');
  const [subject, setSubject] = useState('sejarah');
  const [mode, setMode] = useState<Mode>('explain');
  const [inputTab, setInputTab] = useState<InputTab>('paste');

  const [paperText, setPaperText] = useState('');
  const [pdfBase64, setPdfBase64] = useState('');
  const [imageBase64, setImageBase64] = useState('');
  const [imageMime, setImageMime] = useState('image/jpeg');
  const [imagePreviewUrl, setImagePreviewUrl] = useState('');
  const [ocrScanning, setOcrScanning] = useState(false);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const [followUp, setFollowUp] = useState('');
  const [quizAnswer, setQuizAnswer] = useState('');
  const [activeQuizIndex, setActiveQuizIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: pastPapers = [] } = useSWR<AgentRunEntry[]>(
    userId ? agentRunsForAgentKey(userId, 'study-agent') : null,
    () => fetchAgentRunsAuthed(supabase, 'study-agent'),
    HISTORY_SWR_OPTIONS,
  );

  const onLevelChange = (next: Level) => {
    setLevel(next);
    setSubject(LEVEL_SUBJECTS[next][0]);
  };

  const onPickImage = async (file: File | null) => {
    if (!file) return;
    setImageMime(file.type || 'image/jpeg');
    const base64 = await fileToBase64(file);
    setImageBase64(base64);
    setImagePreviewUrl(URL.createObjectURL(file));

    // Client-side OCR pass: instant editable preview, and the offline/
    // vision-LLM-failure fallback — the backend photo path (vision-LLM) is
    // still the primary extraction, this just gives the student something
    // to see and edit immediately instead of a blank textarea while
    // waiting on the network call.
    setOcrScanning(true);
    try {
      const Tesseract = await import('tesseract.js');
      const { data } = await Tesseract.recognize(file, 'eng+msa');
      if (data.text.trim()) setPaperText(data.text.trim());
    } catch {
      /* best-effort only — backend vision OCR remains the real path */
    } finally {
      setOcrScanning(false);
    }
  };

  const onPickPdf = async (file: File | null) => {
    if (!file) return;
    setPdfBase64(await fileToBase64(file));
  };

  const runStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await start('study-agent', {
        level,
        subject,
        mode,
        paper_text: paperText,
        document_base64: inputTab === 'pdf' ? pdfBase64 : '',
        image_base64: inputTab === 'photo' ? imageBase64 : '',
        image_mime_type: imageMime,
        language: 'bm',
      });
      setSessionId(String(res.session_id));
      setOutput((res.output as Record<string, unknown>) ?? res);
      setActiveQuizIndex(0);
      setQuizAnswer('');
    } catch (e) {
      setError(e instanceof Error ? e.message : t('agents.error.generic'));
    } finally {
      setLoading(false);
    }
  };

  const runContinue = async (message: string, questionIndex?: number) => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await cont('study-agent', {
        session_id: sessionId,
        message,
        ...(questionIndex !== undefined ? { question_index: questionIndex } : {}),
      });
      setOutput((res.output as Record<string, unknown>) ?? res);
    } catch {
      setError(t('agents.error.generic'));
    } finally {
      setLoading(false);
    }
  };

  const submitQuizAnswer = async () => {
    if (!quizAnswer.trim()) return;
    await runContinue(quizAnswer, activeQuizIndex);
    setQuizAnswer('');
  };

  // Resume from History's "?run=<agent_runs.id>" link.
  useEffect(() => {
    const runId = searchParams.get('run');
    if (!runId) return;
    (async () => {
      try {
        const run = await get(`/api/v1/agent-runs/${runId}`);
        setOutput((run.output as Record<string, unknown>) ?? {});
        setSessionId(typeof run.session_id === 'string' ? run.session_id : null);
      } catch {
        /* stale/invalid run id — stays on the fresh intake flow */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const explanations = (output?.explanations as Array<Record<string, unknown>>) ?? [];
  const topics = output?.topic_progress as Record<string, number> | undefined;
  const quiz = (output?.quiz as QuizItem[]) ?? [];
  const quizScore = Number(output?.quiz_score ?? 0);
  const quizAnswered = Number(output?.quiz_answered ?? 0);
  const currentQuizItem = quiz[activeQuizIndex];

  const inputTabClass = (tab: InputTab) =>
    `px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
      inputTab === tab
        ? 'bg-nk-official text-white'
        : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-white/5 dark:text-zinc-400 dark:hover:bg-white/10'
    }`;

  const canSubmit =
    !loading &&
    ((inputTab === 'paste' && paperText.trim().length > 0) ||
      (inputTab === 'pdf' && pdfBase64.length > 0) ||
      (inputTab === 'photo' && imageBase64.length > 0));

  return (
    <>
      <AgentPageHeader title={t(agentTitleKey('study-agent'))} />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="max-w-2xl mx-auto p-4 flex flex-col gap-4"
      >
        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/30">
            {error}
          </p>
        )}

        <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
          <div className="flex flex-wrap gap-3">
            <div className="flex flex-col gap-1 flex-1 min-w-[120px]">
              <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                {t('agents.study-agent.level.label')}
              </label>
              <select
                className="border border-zinc-200 rounded-lg p-2 text-sm bg-transparent transition-colors focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10"
                value={level}
                onChange={(e) => onLevelChange(e.target.value as Level)}
              >
                {(['spm', 'stpm', 'a-level'] as Level[]).map((lvl) => (
                  <option key={lvl} value={lvl} className="text-zinc-900">
                    {t(`agents.study-agent.level.${lvl}`)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1 flex-1 min-w-[120px]">
              <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Subject</label>
              <select
                className="border border-zinc-200 rounded-lg p-2 text-sm bg-transparent transition-colors focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              >
                {LEVEL_SUBJECTS[level].map((s) => (
                  <option key={s} value={s} className="text-zinc-900">
                    {s.replace('_', ' ')}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex gap-2">
            {(['explain', 'quiz'] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
                  mode === m
                    ? 'bg-nk-official text-white'
                    : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-white/5 dark:text-zinc-400 dark:hover:bg-white/10'
                }`}
              >
                {t(`agents.study-agent.mode.${m}`)}
              </button>
            ))}
          </div>

          <div className="flex gap-2 pt-1">
            <button type="button" className={inputTabClass('paste')} onClick={() => setInputTab('paste')}>
              {t('agents.study-agent.input.paste')}
            </button>
            <button type="button" className={inputTabClass('pdf')} onClick={() => setInputTab('pdf')}>
              {t('agents.study-agent.input.upload_pdf')}
            </button>
            <button type="button" className={inputTabClass('photo')} onClick={() => setInputTab('photo')}>
              {t('agents.study-agent.input.scan_photo')}
            </button>
          </div>

          {inputTab === 'paste' && (
            <textarea
              className="border border-zinc-200 rounded-xl p-3 text-sm min-h-[120px] bg-transparent transition-colors focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10 dark:placeholder:text-zinc-500"
              value={paperText}
              onChange={(e) => setPaperText(e.target.value)}
              placeholder={t('agents.study-agent.paste_placeholder')}
            />
          )}

          {inputTab === 'pdf' && (
            <div className="flex flex-col gap-2">
              <label className="text-xs text-zinc-500 dark:text-zinc-400">{t('agents.study-agent.upload_pdf_label')}</label>
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => void onPickPdf(e.target.files?.[0] ?? null)}
                className="text-sm text-zinc-600 dark:text-zinc-400"
              />
              {pdfBase64 && <p className="text-xs text-green-600 dark:text-green-400">✓ PDF ready</p>}
            </div>
          )}

          {inputTab === 'photo' && (
            <div className="flex flex-col gap-2">
              <label className="text-xs text-zinc-500 dark:text-zinc-400">{t('agents.study-agent.scan_photo_label')}</label>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(e) => void onPickImage(e.target.files?.[0] ?? null)}
                className="text-sm text-zinc-600 dark:text-zinc-400"
              />
              {imagePreviewUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imagePreviewUrl} alt="" className="max-h-40 rounded-lg border border-zinc-200 dark:border-white/10 object-contain" />
              )}
              {ocrScanning && <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('agents.study-agent.ocr_scanning')}</p>}
              {imageBase64 && !ocrScanning && (
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-zinc-500 dark:text-zinc-400">{t('agents.study-agent.ocr_preview_label')}</label>
                  <textarea
                    className="border border-zinc-200 rounded-xl p-3 text-sm min-h-[100px] bg-transparent transition-colors focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10"
                    value={paperText}
                    onChange={(e) => setPaperText(e.target.value)}
                  />
                </div>
              )}
            </div>
          )}

          <button
            type="button"
            disabled={!canSubmit}
            onClick={() => void runStart()}
            className="self-end px-4 py-2 bg-nk-official hover:bg-nk-official-dim hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 text-white rounded-xl text-sm font-semibold shadow-sm shadow-blue-900/20 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading
              ? t('agents.study-agent.analysing')
              : mode === 'quiz'
                ? t('agents.study-agent.submit_quiz')
                : t('agents.study-agent.submit_explain')}
          </button>
        </section>

        {mode === 'explain' && explanations.length > 0 && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
            <h2 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">{t('agents.study-agent.explanations_title')}</h2>
            {explanations.map((ex, i) => (
              <div key={i} className="border-b border-zinc-100 pb-3 text-sm last:border-b-0 last:pb-0 dark:border-white/10">
                <p className="font-medium text-zinc-800 dark:text-zinc-200">{String(ex.question)}</p>
                <p className="text-zinc-600 mt-1 leading-relaxed dark:text-zinc-400">{String(ex.explanation)}</p>
              </div>
            ))}
            {topics && (
              <div className="text-xs text-zinc-500 dark:text-zinc-400">
                {t('agents.study-agent.topics_label')}: {Object.entries(topics).map(([k, v]) => `${k.replace('_', ' ')} (${v})`).join(', ')}
              </div>
            )}
            <input
              className="border border-zinc-200 rounded-lg p-2 text-sm bg-transparent transition-colors focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10 dark:placeholder:text-zinc-500"
              placeholder={t('agents.study-agent.follow_up_placeholder')}
              value={followUp}
              onChange={(e) => setFollowUp(e.target.value)}
            />
            <button
              type="button"
              onClick={() => void runContinue(followUp)}
              className="self-end text-sm text-nk-official-dim hover:text-nk-official-dim hover:underline transition-colors dark:text-nk-official dark:hover:text-nk-official"
            >
              {t('agents.study-agent.follow_up_button')}
            </button>
          </section>
        )}

        {mode === 'quiz' && quiz.length > 0 && (
          <section className="bg-white border border-zinc-200 rounded-2xl p-4 flex flex-col gap-3 shadow-[0_2px_16px_rgba(15,23,42,0.06)] dark:bg-white/5 dark:border-white/10">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">{t('agents.study-agent.quiz.title')}</h2>
              <span className="text-xs font-semibold text-nk-official">
                {fmt(t('agents.study-agent.quiz.score'), { n: quizScore, m: quizAnswered })}
              </span>
            </div>

            {currentQuizItem ? (
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{currentQuizItem.question}</p>

                {currentQuizItem.verdict ? (
                  <div className="flex flex-col gap-2">
                    <p
                      className={`text-sm font-semibold ${
                        currentQuizItem.verdict.correct
                          ? 'text-green-600 dark:text-green-400'
                          : currentQuizItem.verdict.partial
                            ? 'text-amber-600 dark:text-amber-400'
                            : 'text-red-600 dark:text-red-400'
                      }`}
                    >
                      {currentQuizItem.verdict.correct
                        ? t('agents.study-agent.quiz.correct')
                        : currentQuizItem.verdict.partial
                          ? t('agents.study-agent.quiz.partial')
                          : t('agents.study-agent.quiz.incorrect')}
                    </p>
                    {currentQuizItem.verdict.feedback && (
                      <p className="text-sm text-zinc-600 dark:text-zinc-400">{currentQuizItem.verdict.feedback}</p>
                    )}
                    {activeQuizIndex < quiz.length - 1 ? (
                      <button
                        type="button"
                        onClick={() => setActiveQuizIndex((i) => i + 1)}
                        className="self-end px-3 py-1.5 bg-nk-official hover:bg-nk-official-dim text-white rounded-lg text-xs font-semibold transition-colors"
                      >
                        {t('agents.study-agent.quiz.next_question')}
                      </button>
                    ) : (
                      <p className="text-sm font-semibold text-nk-official">
                        {fmt(t('agents.study-agent.quiz.done'), { n: quizScore, m: quiz.length })}
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <textarea
                      className="border border-zinc-200 rounded-xl p-3 text-sm min-h-[80px] bg-transparent transition-colors focus:border-nk-official/50 focus:outline-none focus:ring-1 focus:ring-nk-official/30 dark:border-white/10 dark:placeholder:text-zinc-500"
                      value={quizAnswer}
                      onChange={(e) => setQuizAnswer(e.target.value)}
                      placeholder={t('agents.study-agent.quiz.answer_placeholder')}
                    />
                    <button
                      type="button"
                      disabled={loading || !quizAnswer.trim()}
                      onClick={() => void submitQuizAnswer()}
                      className="self-end px-3 py-1.5 bg-nk-official hover:bg-nk-official-dim text-white rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
                    >
                      {t('agents.study-agent.quiz.submit_answer')}
                    </button>
                  </div>
                )}
              </div>
            ) : null}
          </section>
        )}

        <section className="flex flex-col gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
            {t('agents.study-agent.my_papers_title')}
          </h2>
          {pastPapers.length === 0 ? (
            <p className="text-xs text-zinc-400 dark:text-zinc-500">{t('agents.study-agent.no_papers')}</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {pastPapers.slice(0, 8).map((run) => (
                <li key={run.id}>
                  <Link
                    href={`/agents/study-agent?run=${encodeURIComponent(run.id)}`}
                    className="block rounded-xl px-3 py-2 text-xs bg-white border border-zinc-100 hover:bg-zinc-50 transition-colors dark:bg-white/5 dark:border-white/10 dark:hover:bg-white/10 dark:text-zinc-300"
                  >
                    {new Date(run.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </motion.div>
    </>
  );
}

export default function StudyAgentPage() {
  return (
    <Suspense>
      <StudyAgentPageInner />
    </Suspense>
  );
}
