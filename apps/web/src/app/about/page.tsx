'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
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
    <div className={`flex flex-col min-h-screen font-sans ${isDark ? 'bg-[#0A0F1E] text-white' : 'bg-zinc-50 text-zinc-900'}`}>
      <LandingHeader />

      <div className="flex flex-col flex-1 min-w-0 max-w-4xl mx-auto w-full px-4 sm:px-6">

        <main className="flex-1 overflow-y-auto px-6 py-12 max-w-4xl mx-auto w-full">
          <motion.div initial="hidden" animate="show" variants={fadeUp} className="space-y-12">
            <header className="text-center space-y-3">
              <h1 className="text-4xl font-bold tracking-tight">{c.title}</h1>
              <p className="text-lg text-zinc-400">{c.subtitle}</p>
            </header>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-blue-400">{c.mission.title}</h2>
              <p className="text-zinc-300 leading-relaxed">{c.mission.desc}</p>
            </section>

            <section className="space-y-6">
              <h2 className="text-2xl font-bold text-blue-400">{c.how.title}</h2>
              <div className="grid md:grid-cols-3 gap-6">
                {c.how.steps.map((step, i) => (
                  <div key={i} className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-2">
                    <div className="w-10 h-10 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-lg">
                      {i + 1}
                    </div>
                    <h3 className="font-semibold text-white">{step.title}</h3>
                    <p className="text-sm text-zinc-400">{step.desc}</p>
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-blue-400">{c.sources.title}</h2>
              <p className="text-zinc-300">{c.sources.desc}</p>
              <ul className="grid md:grid-cols-2 gap-3">
                {c.sources.items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-zinc-300">
                    <svg className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-blue-400">{c.tech.title}</h2>
              <p className="text-zinc-300">{c.tech.desc}</p>
              <ul className="space-y-2">
                {c.tech.items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-zinc-300">
                    <svg className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
            </section>

            <section className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-6 space-y-3">
              <div className="flex items-center gap-2">
                <svg className="w-6 h-6 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
                <h2 className="text-xl font-bold text-amber-300">{c.disclaimer.title}</h2>
              </div>
              <p className="text-zinc-300 leading-relaxed">{c.disclaimer.desc}</p>
            </section>

            <div className="flex justify-center pt-6">
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 transition-colors text-white font-semibold px-8 py-3.5 rounded-full shadow-lg shadow-blue-900/40"
              >
                {t('landing.hero.cta')}
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z" clipRule="evenodd" />
                </svg>
              </Link>
            </div>
          </motion.div>
        </main>

        <footer className="border-t border-white/10 px-6 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-zinc-500">
          <span className="locale-nowrap">&copy; 2026 NakTahu AI</span>
          <div className="flex items-center gap-4">
            <Link href="/" className="hover:text-white transition-colors">{t('nav.home')}</Link>
            <Link href="/privacy" className="hover:text-white transition-colors">{t('footer.privacy')}</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
