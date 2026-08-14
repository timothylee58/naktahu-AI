'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function AboutPage() {
  const { t, locale } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const reduceMotion = useReducedMotion();
  const sealLabel = locale === 'zh' ? '已验证 · LHDN.gov.my' : locale === 'en' ? 'Verified · LHDN.gov.my' : 'Disahkan · LHDN.gov.my';

  const content = {
    ms: {
      title: 'Tentang NakTahu AI',
      subtitle: 'Ilmu tempatan, jawapan seketika.',
      mission: {
        title: 'Misi Kami',
        desc: 'NakTahu AI dicipta untuk memudahkan akses rakyat Malaysia kepada maklumat kerajaan yang sahih. Kami percaya setiap rakyat berhak mendapat jawapan yang tepat, cepat, dan berdasarkan sumber rasmi.',
      },
      how: {
        title: 'Bagaimana Ia Berfungsi',
        steps: [
          { title: 'Tanya Soalan', desc: 'Taip soalan anda dalam Bahasa Malaysia, English, atau Mandarin' },
          { title: 'Analisis Pintar', desc: 'AI kami mencari dan menganalisis dokumen rasmi kerajaan yang berkaitan' },
          { title: 'Jawapan Bersumber', desc: 'Dapatkan jawapan tepat dengan pautan ke dokumen asal' },
        ],
      },
      sources: {
        title: 'Sumber Data',
        desc: 'Semua jawapan berdasarkan dokumen rasmi dari:',
        items: [
          'Portal rasmi kerajaan Malaysia (gov.my)',
          'Lembaga Hasil Dalam Negeri (LHDN)',
          'Kumpulan Wang Simpanan Pekerja (KWSP)',
          'Suruhanjaya Syarikat Malaysia (SSM)',
          'Kementerian Pendidikan Malaysia (KPM)',
          'Jabatan Imigresen Malaysia',
        ],
      },
      tech: {
        title: 'Teknologi',
        desc: 'NakTahu AI dibangunkan menggunakan teknologi terkini:',
        items: [
          'Retrieval-Augmented Generation (RAG) untuk jawapan yang tepat',
          'Pengecaman bahasa automatik (BM, EN, ZH)',
          'Vector search dengan pgvector untuk carian semantik',
          'Streaming responses untuk pengalaman yang pantas',
        ],
      },
      disclaimer: {
        title: 'Penafian',
        desc: 'NakTahu AI adalah projek portfolio dan bukan perkhidmatan rasmi kerajaan. Sentiasa rujuk portal rasmi kerajaan untuk maklumat terkini dan nasihat undang-undang profesional untuk keputusan penting.',
      },
    },
    en: {
      title: 'About NakTahu AI',
      subtitle: 'Local knowledge, instant answers.',
      mission: {
        title: 'Our Mission',
        desc: 'NakTahu AI was created to make it easier for Malaysians to access verified government information. We believe every citizen deserves accurate, fast answers grounded in official sources.',
      },
      how: {
        title: 'How It Works',
        steps: [
          { title: 'Ask a Question', desc: 'Type your question in Bahasa Malaysia, English, or Mandarin' },
          { title: 'Smart Analysis', desc: 'Our AI searches and analyzes relevant official government documents' },
          { title: 'Cited Answers', desc: 'Get accurate answers with links to original documents' },
        ],
      },
      sources: {
        title: 'Data Sources',
        desc: 'All answers are based on official documents from:',
        items: [
          'Official Malaysian government portals (gov.my)',
          'Inland Revenue Board (LHDN)',
          'Employees Provident Fund (EPF/KWSP)',
          'Companies Commission of Malaysia (SSM)',
          'Ministry of Education Malaysia (MOE)',
          'Immigration Department of Malaysia',
        ],
      },
      tech: {
        title: 'Technology',
        desc: 'NakTahu AI is built using cutting-edge technology:',
        items: [
          'Retrieval-Augmented Generation (RAG) for accurate answers',
          'Automatic language detection (BM, EN, ZH)',
          'Vector search with pgvector for semantic search',
          'Streaming responses for fast experience',
        ],
      },
      disclaimer: {
        title: 'Disclaimer',
        desc: 'NakTahu AI is a portfolio project and not an official government service. Always refer to official government portals for the latest information and consult professional legal advice for important decisions.',
      },
    },
    zh: {
      title: '关于 NakTahu AI',
      subtitle: '本地知识，即时解答。',
      mission: {
        title: '我们的使命',
        desc: 'NakTahu AI 旨在让马来西亚人更容易获取经过验证的政府信息。我们相信每位公民都应该获得基于官方来源的准确、快速答案。',
      },
      how: {
        title: '工作原理',
        steps: [
          { title: '提出问题', desc: '用马来语、英语或中文输入您的问题' },
          { title: '智能分析', desc: '我们的 AI 搜索并分析相关的官方政府文件' },
          { title: '引用答案', desc: '获得带有原始文档链接的准确答案' },
        ],
      },
      sources: {
        title: '数据来源',
        desc: '所有答案均基于以下官方文件：',
        items: [
          '马来西亚官方政府门户网站 (gov.my)',
          '国内税收局 (LHDN)',
          '雇员公积金 (EPF/KWSP)',
          '马来西亚公司委员会 (SSM)',
          '马来西亚教育部 (MOE)',
          '马来西亚移民局',
        ],
      },
      tech: {
        title: '技术',
        desc: 'NakTahu AI 采用尖端技术构建：',
        items: [
          '检索增强生成 (RAG) 以获得准确答案',
          '自动语言检测 (马来语、英语、中文)',
          '使用 pgvector 进行向量搜索以实现语义搜索',
          '流式响应以获得快速体验',
        ],
      },
      disclaimer: {
        title: '免责声明',
        desc: 'NakTahu AI 是一个作品集项目，不是官方政府服务。请始终参考官方政府门户网站获取最新信息，并就重要决定咨询专业法律建议。',
      },
    },
  };

  const c = locale === 'zh' ? content.zh : locale === 'en' ? content.en : content.ms;

  return (
    <div className={`flex flex-col h-full font-sans ${isDark ? 'bg-[#12151C] text-white' : 'bg-zinc-50 text-zinc-900'}`}>
      <LandingHeader />

      <div className="flex flex-col flex-1 min-w-0 min-h-0 max-w-4xl mx-auto w-full px-4 sm:px-6">

        <main className="flex-1 min-h-0 overflow-y-auto px-6 py-12 max-w-4xl mx-auto w-full">
          <motion.div initial="hidden" animate="show" variants={fadeUp} className="space-y-12">
            <header className="text-center space-y-3">
              <h1 className="text-4xl font-bold tracking-tight">{c.title}</h1>
              <p className={`text-lg ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{c.subtitle}</p>
            </header>

            <motion.section
              className="space-y-4"
              initial={reduceMotion ? false : { opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.5 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
            >
              <h2 className={`text-2xl font-bold ${isDark ? 'text-nk-official' : 'text-nk-official-dim'}`}>{c.mission.title}</h2>
              <p className={`leading-relaxed ${isDark ? 'text-zinc-300' : 'text-zinc-600'}`}>{c.mission.desc}</p>
            </motion.section>

            <section className="space-y-6">
              <h2 className={`text-2xl font-bold ${isDark ? 'text-nk-official' : 'text-nk-official-dim'}`}>{c.how.title}</h2>
              <div className="relative">
                {/* Connecting line — draws left-to-right as the row scrolls into view.
                    Desktop only (the grid is single-column below md, where a horizontal
                    line between stacked cards wouldn't read as a sequence). */}
                <motion.div
                  aria-hidden
                  initial={reduceMotion ? false : { scaleX: 0 }}
                  whileInView={{ scaleX: 1 }}
                  viewport={{ once: true, amount: 0.6 }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                  style={{ transformOrigin: 'left' }}
                  className={`hidden md:block absolute top-5 left-[16.66%] right-[16.66%] h-px ${
                    isDark ? 'bg-nk-official/30' : 'bg-nk-official/30'
                  }`}
                />
                <div className="grid md:grid-cols-3 gap-6">
                  {c.how.steps.map((step, i) => (
                    <motion.div
                      key={i}
                      initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true, amount: 0.5 }}
                      transition={{ duration: 0.45, delay: reduceMotion ? 0 : i * 0.15, ease: 'easeOut' }}
                      className={`relative rounded-xl p-6 space-y-2 border ${
                        isDark ? 'bg-white/5 border-white/10' : 'bg-white border-zinc-200 shadow-sm'
                      }`}
                    >
                      <div className={`relative z-10 w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg ${
                        isDark ? 'bg-nk-official/20 text-nk-official' : 'bg-nk-official/20 text-nk-official-dim'
                      }`}>
                        {i + 1}
                      </div>
                      <h3 className={`font-semibold ${isDark ? 'text-white' : 'text-zinc-900'}`}>{step.title}</h3>
                      <p className={`text-sm ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{step.desc}</p>
                      {i === c.how.steps.length - 1 && (
                        // Makes the "we cite official sources" claim visible at the
                        // exact moment a reader would otherwise just read it as a
                        // sentence — the one deliberate flourish on this page.
                        // Decorative only: no meaning conveyed by color alone.
                        <motion.span
                          initial={reduceMotion ? false : { opacity: 0, scale: 0.85 }}
                          whileInView={{ opacity: 1, scale: 1 }}
                          viewport={{ once: true, amount: 0.6 }}
                          // No spring/bounce — this seal backs a trust claim (official
                          // sourcing), and this product's whole pitch is "calm and
                          // precise, not playful." Short ease-out only.
                          transition={{ duration: 0.25, ease: 'easeOut', delay: reduceMotion ? 0 : 0.35 }}
                          className={`absolute -top-2 -right-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide shadow-sm ${
                            isDark ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300' : 'bg-emerald-50 border-emerald-300 text-emerald-700'
                          }`}
                        >
                          {sealLabel}
                        </motion.span>
                      )}
                    </motion.div>
                  ))}
                </div>
              </div>
            </section>

            {/* Trust signal — a distinct green-tinted card treatment with checkmarks,
                so it reads visually as "these are the sources backing every answer"
                rather than looking like the (differently-styled) engineering list
                below it. */}
            <section className="space-y-4">
              <h2 className={`text-2xl font-bold ${isDark ? 'text-nk-official' : 'text-nk-official-dim'}`}>{c.sources.title}</h2>
              <p className={isDark ? 'text-zinc-300' : 'text-zinc-600'}>{c.sources.desc}</p>
              <ul className={`grid md:grid-cols-2 gap-3 rounded-xl border p-4 ${
                isDark ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-emerald-50/60 border-emerald-200'
              }`}>
                {c.sources.items.map((item, i) => (
                  <motion.li
                    key={i}
                    initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, amount: 0.6 }}
                    transition={{ duration: 0.25, ease: 'easeOut', delay: reduceMotion ? 0 : i * 0.04 }}
                    className={`flex items-start gap-2 ${isDark ? 'text-zinc-300' : 'text-zinc-700'}`}
                  >
                    <svg className={`w-5 h-5 mt-0.5 flex-shrink-0 ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`} fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                    </svg>
                    {item}
                  </motion.li>
                ))}
              </ul>
            </section>

            {/* Engineering-credibility list — a distinct slate/monospace treatment
                so it doesn't visually blend with the trust-signal card above it. */}
            <section className="space-y-4">
              <h2 className={`text-2xl font-bold ${isDark ? 'text-nk-official' : 'text-nk-official-dim'}`}>{c.tech.title}</h2>
              <p className={isDark ? 'text-zinc-300' : 'text-zinc-600'}>{c.tech.desc}</p>
              <ul className={`space-y-2 rounded-xl border p-4 ${
                isDark ? 'bg-white/[0.03] border-white/10' : 'bg-zinc-50 border-zinc-200'
              }`}>
                {c.tech.items.map((item, i) => (
                  <motion.li
                    key={i}
                    initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, amount: 0.6 }}
                    transition={{ duration: 0.25, ease: 'easeOut', delay: reduceMotion ? 0 : i * 0.04 }}
                    className={`flex items-start gap-2 font-mono text-sm ${isDark ? 'text-zinc-300' : 'text-zinc-600'}`}
                  >
                    <svg className={`w-5 h-5 mt-0.5 flex-shrink-0 ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`} fill="currentColor" viewBox="0 0 20 20" aria-hidden>
                      <path fillRule="evenodd" d="M6.28 5.22a.75.75 0 010 1.06L2.56 10l3.72 3.72a.75.75 0 01-1.06 1.06L.97 10.53a.75.75 0 010-1.06l4.25-4.25a.75.75 0 011.06 0zm7.44 0a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06-1.06L17.44 10l-3.72-3.72a.75.75 0 010-1.06z" clipRule="evenodd" />
                    </svg>
                    {item}
                  </motion.li>
                ))}
              </ul>
            </section>

            <section className={`rounded-xl p-6 space-y-3 border ${
              isDark ? 'bg-amber-500/10 border-amber-500/20' : 'bg-amber-50 border-amber-200'
            }`}>
              <div className="flex items-center gap-2">
                <svg className={`w-6 h-6 ${isDark ? 'text-amber-400' : 'text-amber-500'}`} fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
                <h2 className={`text-xl font-bold ${isDark ? 'text-amber-300' : 'text-amber-700'}`}>{c.disclaimer.title}</h2>
              </div>
              <p className={`leading-relaxed ${isDark ? 'text-zinc-300' : 'text-zinc-600'}`}>{c.disclaimer.desc}</p>
            </section>

            <div className="flex justify-center pt-6">
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 bg-nk-official hover:bg-nk-official-dim transition-colors text-white font-semibold px-8 py-3.5 rounded-full shadow-lg shadow-blue-900/40"
              >
                {t('landing.hero.cta')}
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z" clipRule="evenodd" />
                </svg>
              </Link>
            </div>
          </motion.div>
        </main>

        <footer className={`border-t px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm ${
          isDark ? 'border-white/10 text-zinc-500' : 'border-zinc-200 text-zinc-500'
        }`}>
          <span className="locale-nowrap">&copy; 2026 NakTahu AI</span>
          <div className="flex items-center gap-4">
            <Link href="/" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-zinc-900'}`}>{t('nav.home')}</Link>
            <Link href="/privacy" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-zinc-900'}`}>{t('footer.privacy')}</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
