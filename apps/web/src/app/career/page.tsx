'use client';

import { useCallback, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useI18n } from '@/lib/i18n';

// ── option data ──────────────────────────────────────────────────────────────

const EDU_OPTIONS = [
  { value: 'spm', ms: 'SPM / Setaraf', en: 'SPM / Equivalent', zh: 'SPM / 同等学历' },
  { value: 'diploma', ms: 'Diploma', en: 'Diploma', zh: '文凭' },
  { value: 'degree', ms: 'Ijazah Sarjana Muda', en: "Bachelor's Degree", zh: '学士学位' },
  { value: 'postgrad', ms: 'Sarjana / PhD', en: "Master's / PhD", zh: '硕士 / 博士' },
  { value: 'none', ms: 'Tiada sijil formal', en: 'No formal certificate', zh: '无正式证书' },
];

const FIELD_OPTIONS = [
  { value: 'tech', ms: 'Teknologi Maklumat', en: 'Information Technology', zh: '信息技术' },
  { value: 'finance', ms: 'Kewangan / Perakaunan', en: 'Finance / Accounting', zh: '金融 / 会计' },
  { value: 'health', ms: 'Penjagaan Kesihatan', en: 'Healthcare', zh: '医疗卫生' },
  { value: 'education', ms: 'Pendidikan', en: 'Education', zh: '教育' },
  { value: 'business', ms: 'Perniagaan / Keusahawanan', en: 'Business / Entrepreneurship', zh: '商业 / 创业' },
  { value: 'creative', ms: 'Kreatif / Seni', en: 'Creative / Arts', zh: '创意 / 艺术' },
  { value: 'other', ms: 'Lain-lain', en: 'Other', zh: '其他' },
];

const STATUS_OPTIONS = [
  { value: 'citizen', ms: 'Warganegara Malaysia', en: 'Malaysian Citizen', zh: '马来西亚公民' },
  { value: 'pr', ms: 'Pemastautin Tetap (PR)', en: 'Permanent Resident (PR)', zh: '永久居民 (PR)' },
  { value: 'expat', ms: 'Ekspatriat / Pemegang Pas Kerja', en: 'Expat / Work Pass Holder', zh: '外籍人士 / 工作准证持有者' },
  { value: 'student', ms: 'Pemegang Pas Pelajar', en: 'Student Pass Holder', zh: '学生准证持有者' },
];

const GOAL_OPTIONS = [
  { value: 'job_switch', ms: 'Tukar kerjaya / industri', en: 'Switch career / industry', zh: '转换职业 / 行业' },
  { value: 'promotion', ms: 'Naik pangkat dalam bidang sedia ada', en: 'Advance in current field', zh: '在现有领域晋升' },
  { value: 'freelance', ms: 'Menjadi freelancer / konsultan', en: 'Become freelancer / consultant', zh: '成为自由职业者 / 顾问' },
  { value: 'business', ms: 'Mulakan perniagaan sendiri', en: 'Start my own business', zh: '创业' },
  { value: 'overseas', ms: 'Bekerja di luar negara', en: 'Work overseas', zh: '到海外工作' },
  { value: 'cert', ms: 'Dapatkan sijil / kelayakan baru', en: 'Gain a new certification', zh: '获取新资格 / 证书' },
];

const TIMELINE_OPTIONS = [
  { value: '3m', ms: '3 bulan', en: '3 months', zh: '3个月' },
  { value: '6m', ms: '6 bulan', en: '6 months', zh: '6个月' },
  { value: '1y', ms: '1 tahun', en: '1 year', zh: '1年' },
  { value: '2y', ms: '2+ tahun', en: '2+ years', zh: '2年以上' },
];

const STATE_OPTIONS = [
  { value: 'kl', ms: 'Kuala Lumpur / Selangor', en: 'KL / Selangor', zh: '吉隆坡 / 雪兰莪' },
  { value: 'penang', ms: 'Pulau Pinang', en: 'Penang', zh: '槟城' },
  { value: 'johor', ms: 'Johor', en: 'Johor', zh: '柔佛' },
  { value: 'sabah', ms: 'Sabah', en: 'Sabah', zh: '沙巴' },
  { value: 'sarawak', ms: 'Sarawak', en: 'Sarawak', zh: '砂拉越' },
  { value: 'other_state', ms: 'Negeri lain', en: 'Other state', zh: '其他州' },
];

const LANG_OPTIONS = [
  { value: 'bm', ms: 'Bahasa Malaysia', en: 'Bahasa Malaysia', zh: '马来语' },
  { value: 'en', ms: 'Inggeris', en: 'English', zh: '英语' },
  { value: 'zh', ms: 'Mandarin', en: 'Mandarin', zh: '中文' },
];

// ── types ────────────────────────────────────────────────────────────────────

interface Step1 { edu: string; field: string; status: string }
interface Step2 { goal: string; timeline: string }
interface Step3 { state: string; lang: string }

// ── helper: option card ───────────────────────────────────────────────────────

function OptionCard({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`w-full text-left px-4 py-3 rounded-xl border text-sm font-medium transition-all ${
        selected
          ? 'border-nk-official/40 bg-nk-official/10 text-nk-official-dim ring-1 ring-nk-official dark:bg-nk-official/15 dark:text-nk-official'
          : 'border-zinc-200 bg-white text-zinc-700 hover:border-nk-official/30 hover:bg-nk-official/10 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300 dark:hover:bg-nk-official/10'
      }`}
    >
      <span className="flex items-center gap-2">
        <span
          className={`w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center ${
            selected ? 'border-nk-official/40 bg-nk-official' : 'border-zinc-300 dark:border-white/20'
          }`}
        >
          {selected && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
        </span>
        {label}
      </span>
    </button>
  );
}

// ── step section ─────────────────────────────────────────────────────────────

function StepSection({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider dark:text-zinc-400">{label}</p>
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}

// ── progress bar ─────────────────────────────────────────────────────────────

function ProgressBar({ step, total }: { step: number; total: number }) {
  return (
    <div role="progressbar" aria-valuenow={step} aria-valuemin={1} aria-valuemax={total} className="flex gap-1.5">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`h-1 flex-1 rounded-full transition-all duration-300 ${
            i < step ? 'bg-nk-official' : 'bg-zinc-200 dark:bg-white/10'
          }`}
        />
      ))}
    </div>
  );
}

// ── query builder ─────────────────────────────────────────────────────────────

function buildQuery(
  s1: Partial<Step1>,
  s2: Partial<Step2>,
  s3: Partial<Step3>,
  locale: string,
): string {
  const find = <T extends { value: string; ms: string; en: string; zh: string }>(
    opts: T[],
    val: string,
  ) => {
    const o = opts.find((x) => x.value === val);
    if (!o) return val;
    return locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en;
  };

  const edu = find(EDU_OPTIONS, s1.edu ?? '');
  const field = find(FIELD_OPTIONS, s1.field ?? '');
  const status = find(STATUS_OPTIONS, s1.status ?? '');
  const goal = find(GOAL_OPTIONS, s2.goal ?? '');
  const timeline = find(TIMELINE_OPTIONS, s2.timeline ?? '');
  const state = find(STATE_OPTIONS, s3.state ?? '');
  const lang = find(LANG_OPTIONS, s3.lang ?? '');

  if (locale === 'zh') {
    return `我是${status}，教育程度为${edu}，目前从事${field}领域。我的职业目标是${goal}，希望在${timeline}内实现，居住在${state}，首选语言是${lang}。请根据马来西亚官方资源，提供具体且逐步的职业行动计划，包括所需的证书、政府援助计划及相关机构。`;
  }
  if (locale === 'ms') {
    return `Saya seorang ${status} dengan kelayakan ${edu}, bekerja dalam bidang ${field}. Matlamat kerjaya saya adalah untuk ${goal} dalam tempoh ${timeline}, berada di ${state}, dan berbahasa ${lang}. Berdasarkan sumber rasmi Malaysia, berikan pelan tindakan kerjaya yang terperinci dan langkah demi langkah, termasuk sijil yang diperlukan, program bantuan kerajaan dan agensi berkaitan.`;
  }
  return `I am a ${status} with a ${edu} qualification, currently working in ${field}. My career goal is to ${goal} within ${timeline}, based in ${state}, preferring ${lang}. Based on official Malaysian government sources, provide a detailed step-by-step career action plan including required certifications, government assistance programmes, and relevant agencies.`;
}

// ── main component ────────────────────────────────────────────────────────────

const TOTAL_STEPS = 3;
const spring = { duration: 0.28, ease: [0.16, 1, 0.3, 1] } as const;

export default function CareerPage() {
  const { t, locale } = useI18n();
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [s1, setS1] = useState<Partial<Step1>>({});
  const [s2, setS2] = useState<Partial<Step2>>({});
  const [s3, setS3] = useState<Partial<Step3>>({});

  const label = (opts: { value: string; ms: string; en: string; zh: string }[], val: string) => {
    const o = opts.find((x) => x.value === val);
    if (!o) return '';
    return locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en;
  };

  const step1Complete = Boolean(s1.edu && s1.field && s1.status);
  const step2Complete = Boolean(s2.goal && s2.timeline);
  const step3Complete = Boolean(s3.state && s3.lang);

  const canAdvance = step === 1 ? step1Complete : step === 2 ? step2Complete : step3Complete;

  const handleGenerate = useCallback(() => {
    const query = buildQuery(s1, s2, s3, locale);
    router.push(`/chat?q=${encodeURIComponent(query)}`);
  }, [s1, s2, s3, locale, router]);

  return (
    <div className="flex-1 min-h-0 overflow-y-auto flex flex-col bg-zinc-50 dark:bg-[#0A0F1E]">
      {/* Header */}
      <header className="bg-white border-b border-zinc-200 px-4 py-3 flex items-center gap-3 sticky top-0 z-10 dark:bg-[#0A0F1E]/90 dark:border-white/10 backdrop-blur-md">
        <Link href="/" aria-label={t('career.back')} className="p-1 rounded-lg hover:bg-zinc-100 text-zinc-500 transition-colors dark:hover:bg-white/10 dark:text-zinc-400">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5" aria-hidden="true">
            <path fillRule="evenodd" d="M17 10a.75.75 0 0 1-.75.75H5.612l4.158 3.96a.75.75 0 1 1-1.04 1.08l-5.5-5.25a.75.75 0 0 1 0-1.08l5.5-5.25a.75.75 0 1 1 1.04 1.08L5.612 9.25H16.25A.75.75 0 0 1 17 10Z" clipRule="evenodd" />
          </svg>
        </Link>
        <div>
          <p className="text-xs font-semibold text-nk-official-dim dark:text-nk-official">{t('career.badge')}</p>
          <p className="text-sm font-bold text-zinc-900 leading-tight dark:text-white">{t('career.hero.title')}</p>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center px-4 py-8">
        <div className="w-full max-w-lg flex flex-col gap-6">
          {/* Progress */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                {t('career.step_of').replace('{n}', String(step)).replace('{total}', String(TOTAL_STEPS))}
              </p>
              {/* Summary chips for completed steps */}
              <div className="flex gap-1.5 flex-wrap justify-end">
                {step > 1 && s1.edu && (
                  <span className="text-[10px] bg-nk-official/20 text-nk-official-dim px-2 py-0.5 rounded-full font-medium dark:bg-nk-official/20 dark:text-nk-official">
                    {label(EDU_OPTIONS, s1.edu)}
                  </span>
                )}
                {step > 2 && s2.goal && (
                  <span className="text-[10px] bg-nk-official/20 text-nk-official-dim px-2 py-0.5 rounded-full font-medium dark:bg-nk-official/20 dark:text-nk-official">
                    {label(GOAL_OPTIONS, s2.goal)}
                  </span>
                )}
              </div>
            </div>
            <ProgressBar step={step} total={TOTAL_STEPS} />
          </div>

          {/* Step content */}
          <AnimatePresence mode="wait">
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={spring}
                className="flex flex-col gap-5"
              >
                <h2 className="font-display text-lg font-bold text-zinc-900 dark:text-white">{t('career.s1.title')}</h2>

                <StepSection label={t('career.s1.edu')}>
                  {EDU_OPTIONS.map((o) => (
                    <OptionCard
                      key={o.value}
                      label={locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en}
                      selected={s1.edu === o.value}
                      onClick={() => setS1((p) => ({ ...p, edu: o.value }))}
                    />
                  ))}
                </StepSection>

                <StepSection label={t('career.s1.field')}>
                  {FIELD_OPTIONS.map((o) => (
                    <OptionCard
                      key={o.value}
                      label={locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en}
                      selected={s1.field === o.value}
                      onClick={() => setS1((p) => ({ ...p, field: o.value }))}
                    />
                  ))}
                </StepSection>

                <StepSection label={t('career.s1.status')}>
                  {STATUS_OPTIONS.map((o) => (
                    <OptionCard
                      key={o.value}
                      label={locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en}
                      selected={s1.status === o.value}
                      onClick={() => setS1((p) => ({ ...p, status: o.value }))}
                    />
                  ))}
                </StepSection>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={spring}
                className="flex flex-col gap-5"
              >
                <h2 className="font-display text-lg font-bold text-zinc-900 dark:text-white">{t('career.s2.title')}</h2>

                <StepSection label={t('career.s2.goal')}>
                  {GOAL_OPTIONS.map((o) => (
                    <OptionCard
                      key={o.value}
                      label={locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en}
                      selected={s2.goal === o.value}
                      onClick={() => setS2((p) => ({ ...p, goal: o.value }))}
                    />
                  ))}
                </StepSection>

                <StepSection label={t('career.s2.timeline')}>
                  {TIMELINE_OPTIONS.map((o) => (
                    <OptionCard
                      key={o.value}
                      label={locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en}
                      selected={s2.timeline === o.value}
                      onClick={() => setS2((p) => ({ ...p, timeline: o.value }))}
                    />
                  ))}
                </StepSection>
              </motion.div>
            )}

            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={spring}
                className="flex flex-col gap-5"
              >
                <h2 className="font-display text-lg font-bold text-zinc-900 dark:text-white">{t('career.s3.title')}</h2>

                <StepSection label={t('career.s3.state')}>
                  {STATE_OPTIONS.map((o) => (
                    <OptionCard
                      key={o.value}
                      label={locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en}
                      selected={s3.state === o.value}
                      onClick={() => setS3((p) => ({ ...p, state: o.value }))}
                    />
                  ))}
                </StepSection>

                <StepSection label={t('career.s3.lang')}>
                  {LANG_OPTIONS.map((o) => (
                    <OptionCard
                      key={o.value}
                      label={locale === 'zh' ? o.zh : locale === 'ms' ? o.ms : o.en}
                      selected={s3.lang === o.value}
                      onClick={() => setS3((p) => ({ ...p, lang: o.value }))}
                    />
                  ))}
                </StepSection>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex gap-3 pt-2">
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep((s) => s - 1)}
                className="flex-1 px-4 py-3 rounded-xl border border-zinc-200 text-sm font-semibold text-zinc-600 hover:bg-zinc-100 transition-colors dark:border-white/10 dark:text-zinc-300 dark:hover:bg-white/5"
              >
                {t('career.back')}
              </button>
            )}
            {step < TOTAL_STEPS ? (
              <button
                type="button"
                disabled={!canAdvance}
                onClick={() => setStep((s) => s + 1)}
                className="flex-1 px-4 py-3 rounded-xl bg-nk-official hover:bg-nk-official-dim text-white text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
              >
                {t('career.next')}
              </button>
            ) : (
              <button
                type="button"
                disabled={!canAdvance}
                onClick={handleGenerate}
                className="flex-1 px-4 py-3 rounded-xl bg-nk-official hover:bg-nk-official-dim text-white text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm flex items-center justify-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                  <path d="M15.98 1.804a1 1 0 0 0-1.96 0l-.24 1.192a1 1 0 0 1-.784.785l-1.192.238a1 1 0 0 0 0 1.962l1.192.238a1 1 0 0 1 .785.785l.238 1.192a1 1 0 0 0 1.962 0l.238-1.192a1 1 0 0 1 .785-.785l1.192-.238a1 1 0 0 0 0-1.962l-1.192-.238a1 1 0 0 1-.785-.785l-.238-1.192ZM6.949 5.684a1 1 0 0 0-1.898 0l-.683 2.051a1 1 0 0 1-.633.633l-2.051.683a1 1 0 0 0 0 1.898l2.051.684a1 1 0 0 1 .633.632l.683 2.051a1 1 0 0 0 1.898 0l.683-2.051a1 1 0 0 1 .633-.633l2.051-.683a1 1 0 0 0 0-1.898l-2.051-.683a1 1 0 0 1-.633-.633L6.95 5.684ZM13.949 13.684a1 1 0 0 0-1.898 0l-.184.551a1 1 0 0 1-.632.633l-.551.183a1 1 0 0 0 0 1.898l.551.184a1 1 0 0 1 .633.632l.183.551a1 1 0 0 0 1.898 0l.184-.551a1 1 0 0 1 .632-.632l.551-.184a1 1 0 0 0 0-1.898l-.551-.183a1 1 0 0 1-.633-.633l-.183-.551Z" />
                </svg>
                {t('career.generate')}
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
