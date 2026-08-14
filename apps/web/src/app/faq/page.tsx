'use client';

import { useState } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';

interface FAQItem {
  question: string;
  answer: string;
  sourceUrl?: string;
}

const SOURCE_LABEL: Record<string, string> = {
  ms: '↗ Lihat sumber rasmi',
  en: '↗ View official source',
  zh: '↗ 查看官方来源',
};

// Groups the 12 flat FAQ items into 3 scannable clusters so a reader
// looking for "is this trustworthy" vs "how do I use it" vs "my account"
// doesn't have to read a single undifferentiated list top to bottom.
// Indices are identical across all three languages (same item order),
// so one index map covers every locale.
const GROUP_INDEXES: number[][] = [
  [0, 1, 2, 6], // Asas / Basics — what it is, cost, languages, voice input
  [3, 4, 5, 9, 10, 11], // Ketepatan & Kepercayaan / Accuracy & Trust
  [7, 8], // Akaun & Privasi / Account & Privacy
];

const GROUP_LABELS: Record<string, string[]> = {
  ms: ['Asas', 'Ketepatan & Kepercayaan', 'Akaun & Privasi'],
  en: ['Basics', 'Accuracy & Trust', 'Account & Privacy'],
  zh: ['基础', '准确性与信任', '账户与隐私'],
};

export default function FAQPage() {
  const { t, locale } = useI18n();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const reduceMotion = useReducedMotion();
  // Only one item open at a time — keeps the long question list scannable
  // instead of letting every answer stack up on the page at once.
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const faqs: Record<string, { title: string; subtitle: string; items: FAQItem[] }> = {
    ms: {
      title: 'Soalan Lazim (FAQ)',
      subtitle: 'Jawapan kepada soalan yang kerap ditanya tentang NakTahu AI',
      items: [
        {
          question: 'Apakah NakTahu AI?',
          answer: 'NakTahu AI adalah enjin jawapan AI yang direka khas untuk menjawab soalan tentang perkhidmatan kerajaan Malaysia. Ia menggunakan teknologi Retrieval-Augmented Generation (RAG) untuk memberikan jawapan tepat berdasarkan dokumen rasmi kerajaan.',
        },
        {
          question: 'Adakah NakTahu AI percuma?',
          answer: 'Ya, NakTahu AI percuma untuk semua pengguna. Pengguna tanpa akaun boleh bertanya sehingga 30 soalan sejam, manakala pengguna berdaftar mendapat had 200 soalan sejam.',
        },
        {
          question: 'Bahasa apa yang disokong?',
          answer: 'NakTahu AI menyokong tiga bahasa: Bahasa Malaysia, English, dan Mandarin (简体中文). Anda boleh bertanya dalam mana-mana bahasa dan mendapat jawapan dalam bahasa yang sama.',
        },
        {
          question: 'Dari mana data jawapan diperolehi?',
          answer: 'Semua jawapan berdasarkan dokumen rasmi dari portal kerajaan Malaysia (gov.my), LHDN, KWSP/EPF, SSM, Kementerian Pendidikan, Jabatan Imigresen, dan agensi kerajaan lain yang sah.',
          sourceUrl: 'https://www.malaysia.gov.my/',
        },
        {
          question: 'Sejauh mana ketepatan jawapan?',
          answer: 'NakTahu AI menggunakan sumber rasmi dan memberikan pautan rujukan untuk setiap jawapan. Walau bagaimanapun, untuk keputusan penting seperti cukai atau undang-undang, sila rujuk portal rasmi atau dapatkan nasihat profesional.',
        },
        {
          question: 'Bolehkah saya mempercayai jawapan untuk keputusan penting?',
          answer: 'NakTahu AI adalah alat bantuan maklumat, bukan nasihat profesional. Untuk keputusan penting berkaitan cukai, undang-undang, atau kewangan, sila rujuk pakar profesional atau agensi kerajaan yang berkaitan.',
        },
        {
          question: 'Bagaimana cara input suara berfungsi?',
          answer: 'Klik ikon mikrofon dan sebut soalan anda. Ciri ini memerlukan pelayar Chrome atau Edge dan kebenaran akses mikrofon. Input suara menyokong Bahasa Malaysia (ms-MY), English (en-MY), dan Mandarin (zh-CN).',
        },
        {
          question: 'Adakah sejarah soalan saya disimpan?',
          answer: 'Pengguna berdaftar boleh melihat sejarah soalan mereka di bahagian sidebar. Sejarah disimpan selama 30 hari. Pengguna tanpa akaun tidak mempunyai sejarah yang disimpan.',
        },
        {
          question: 'Bagaimana cara mendaftar akaun?',
          answer: 'Klik butang "Daftar / Masuk" di sidebar. Anda boleh mendaftar menggunakan Google, Microsoft, atau emel. Pendaftaran membolehkan anda menyimpan sejarah soalan dan mendapat had pertanyaan yang lebih tinggi.',
        },
        {
          question: 'Apakah confidence score?',
          answer: 'Confidence score menunjukkan sejauh mana AI yakin dengan jawapannya berdasarkan kualiti dokumen yang ditemui. Jika skor rendah (<0.4), amaran akan dipaparkan dan anda digalakkan menyemak pautan rujukan.',
        },
        {
          question: 'Bolehkah NakTahu AI menjawab soalan peribadi saya?',
          answer: 'Tidak. NakTahu AI hanya menjawab soalan umum tentang perkhidmatan kerajaan. Ia tidak mempunyai akses kepada data peribadi anda atau kes khusus anda. Untuk perkara peribadi, hubungi agensi berkaitan secara terus.',
        },
        {
          question: 'Bagaimana saya melaporkan jawapan yang salah?',
          answer: 'Setiap jawapan mempunyai butang maklum balas (thumbs up/down). Klik thumbs down dan berikan komen untuk membantu kami memperbaiki sistem. Anda juga boleh menyemak pautan rujukan yang diberikan.',
        },
      ],
    },
    en: {
      title: 'Frequently Asked Questions (FAQ)',
      subtitle: 'Answers to common questions about NakTahu AI',
      items: [
        {
          question: 'What is NakTahu AI?',
          answer: 'NakTahu AI is an AI-powered answer engine specifically designed to answer questions about Malaysian government services. It uses Retrieval-Augmented Generation (RAG) technology to provide accurate answers based on official government documents.',
        },
        {
          question: 'Is NakTahu AI free?',
          answer: 'Yes, NakTahu AI is free for all users. Anonymous users can ask up to 30 questions per hour, while registered users get a limit of 200 questions per hour.',
        },
        {
          question: 'What languages are supported?',
          answer: 'NakTahu AI supports three languages: Bahasa Malaysia, English, and Mandarin (简体中文). You can ask in any language and receive answers in the same language.',
        },
        {
          question: 'Where does the answer data come from?',
          answer: 'All answers are based on official documents from Malaysian government portals (gov.my), LHDN, EPF/KWSP, SSM, Ministry of Education, Immigration Department, and other verified government agencies.',
          sourceUrl: 'https://www.malaysia.gov.my/',
        },
        {
          question: 'How accurate are the answers?',
          answer: 'NakTahu AI uses official sources and provides reference links for every answer. However, for important decisions such as tax or legal matters, please refer to official portals or seek professional advice.',
        },
        {
          question: 'Can I trust the answers for important decisions?',
          answer: 'NakTahu AI is an information assistance tool, not professional advice. For important decisions related to tax, legal, or financial matters, please consult professional experts or the relevant government agencies.',
        },
        {
          question: 'How does voice input work?',
          answer: 'Click the microphone icon and speak your question. This feature requires Chrome or Edge browser and microphone access permission. Voice input supports Bahasa Malaysia (ms-MY), English (en-MY), and Mandarin (zh-CN).',
        },
        {
          question: 'Is my question history saved?',
          answer: 'Registered users can view their question history in the sidebar. History is saved for 30 days. Anonymous users do not have saved history.',
        },
        {
          question: 'How do I register an account?',
          answer: 'Click the "Register / Login" button in the sidebar. You can register using Google, Microsoft, or email. Registration allows you to save question history and get a higher query limit.',
        },
        {
          question: 'What is the confidence score?',
          answer: 'The confidence score indicates how confident the AI is in its answer based on the quality of documents found. If the score is low (<0.4), a warning will be displayed and you are encouraged to check the reference links.',
        },
        {
          question: 'Can NakTahu AI answer my personal questions?',
          answer: 'No. NakTahu AI only answers general questions about government services. It does not have access to your personal data or specific cases. For personal matters, contact the relevant agency directly.',
        },
        {
          question: 'How do I report incorrect answers?',
          answer: 'Each answer has feedback buttons (thumbs up/down). Click thumbs down and provide comments to help us improve the system. You can also check the reference links provided.',
        },
      ],
    },
    zh: {
      title: '常见问题 (FAQ)',
      subtitle: '关于 NakTahu AI 的常见问题解答',
      items: [
        {
          question: '什么是 NakTahu AI？',
          answer: 'NakTahu AI 是专门设计用于回答马来西亚政府服务问题的 AI 问答引擎。它使用检索增强生成 (RAG) 技术，基于官方政府文件提供准确答案。',
        },
        {
          question: 'NakTahu AI 是免费的吗？',
          answer: '是的，NakTahu AI 对所有用户免费。匿名用户每小时最多可提问 30 个问题，注册用户每小时最多可提问 200 个问题。',
        },
        {
          question: '支持哪些语言？',
          answer: 'NakTahu AI 支持三种语言：马来语、英语和中文（简体中文）。您可以用任何语言提问，并以相同语言获得答案。',
        },
        {
          question: '答案数据来自哪里？',
          answer: '所有答案均基于马来西亚政府门户网站 (gov.my)、国内税收局、雇员公积金、公司委员会、教育部、移民局和其他经过验证的政府机构的官方文件。',
          sourceUrl: 'https://www.malaysia.gov.my/',
        },
        {
          question: '答案准确度如何？',
          answer: 'NakTahu AI 使用官方来源，并为每个答案提供参考链接。但对于税务或法律等重要决定，请参考官方门户或寻求专业建议。',
        },
        {
          question: '我可以信赖答案来做重要决定吗？',
          answer: 'NakTahu AI 是信息辅助工具，而非专业建议。对于与税务、法律或金融相关的重要决定，请咨询专业专家或相关政府机构。',
        },
        {
          question: '语音输入如何工作？',
          answer: '点击麦克风图标并说出您的问题。此功能需要 Chrome 或 Edge 浏览器以及麦克风访问权限。语音输入支持马来语 (ms-MY)、英语 (en-MY) 和中文 (zh-CN)。',
        },
        {
          question: '我的问题历史会被保存吗？',
          answer: '注册用户可以在侧边栏中查看他们的问题历史。历史记录保存 30 天。匿名用户没有保存的历史记录。',
        },
        {
          question: '如何注册账户？',
          answer: '点击侧边栏中的"注册/登录"按钮。您可以使用 Google、Microsoft 或电子邮件注册。注册后可以保存问题历史并获得更高的查询限制。',
        },
        {
          question: '什么是置信度分数？',
          answer: '置信度分数表示 AI 根据找到的文档质量对答案的信心程度。如果分数较低 (<0.4)，将显示警告，建议您查看参考链接。',
        },
        {
          question: 'NakTahu AI 可以回答我的个人问题吗？',
          answer: '不能。NakTahu AI 只回答有关政府服务的一般问题。它无法访问您的个人数据或具体案例。对于个人事务，请直接联系相关机构。',
        },
        {
          question: '如何报告错误答案？',
          answer: '每个答案都有反馈按钮（竖起/竖下大拇指）。点击竖下大拇指并提供评论以帮助我们改进系统。您还可以查看提供的参考链接。',
        },
      ],
    },
  };

  const content = locale === 'zh' ? faqs.zh : locale === 'en' ? faqs.en : faqs.ms;

  return (
    <div className={`flex flex-col h-full font-sans ${isDark ? 'bg-[#12151C] text-white' : 'bg-zinc-50 text-zinc-900'}`}>
      <LandingHeader />

      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        <main className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 py-10 sm:py-12 max-w-3xl mx-auto w-full">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-8"
          >
            <header className="text-center space-y-3">
              <h1 className="text-4xl font-bold tracking-tight">{content.title}</h1>
              <p className={`text-lg ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}>{content.subtitle}</p>
            </header>

            {GROUP_INDEXES.map((group, groupIdx) => (
              <div key={groupIdx} className="space-y-3">
                <h2 className={`text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-zinc-500' : 'text-zinc-400'}`}>
                  {(GROUP_LABELS[locale] ?? GROUP_LABELS.en)[groupIdx]}
                </h2>
                {group.map((index) => {
                  const faq = content.items[index];
                  return (
                    <motion.div
                      key={index}
                      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: reduceMotion ? 0 : index * 0.04, duration: 0.3, ease: 'easeOut' }}
                      className={`rounded-xl overflow-hidden border ${
                        isDark ? 'bg-white/5 border-white/10' : 'bg-white border-zinc-200 shadow-sm'
                      }`}
                    >
                      <button
                        onClick={() => setOpenIndex(openIndex === index ? null : index)}
                        aria-expanded={openIndex === index}
                        className={`w-full flex items-center justify-between px-6 py-4 text-left transition-colors ${
                          isDark ? 'hover:bg-white/5' : 'hover:bg-zinc-50'
                        }`}
                      >
                        <span className={`font-semibold pr-4 ${isDark ? 'text-white' : 'text-zinc-900'}`}>{faq.question}</span>
                        <svg
                          style={{
                            transform: `rotate(${openIndex === index ? 135 : 0}deg)`,
                            transition: reduceMotion ? 'none' : 'transform 0.15s ease-out',
                          }}
                          className={`w-5 h-5 flex-shrink-0 ${isDark ? 'text-zinc-400' : 'text-zinc-500'}`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          aria-hidden
                        >
                          {/* A "+" that rotates into an "×" reads as opening/closing a
                              panel, not just flipping a chevron. */}
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                      </button>

                      {/* grid-template-rows 0fr -> 1fr instead of height:auto / max-height
                          hacks — the inner content's real height animates smoothly with no
                          snap or overshoot, and no exit-animation choreography is needed.
                          Only the interacted panel's rows value changes on any given
                          click — siblings that are already open/closed don't re-render
                          their transition, so there's no visual noise from neighbors. */}
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateRows: openIndex === index ? '1fr' : '0fr',
                          transition: reduceMotion ? 'none' : 'grid-template-rows 0.2s ease-out',
                        }}
                      >
                        <div className="overflow-hidden">
                          <div className={`px-6 pb-4 leading-relaxed flex flex-col gap-2 ${isDark ? 'text-zinc-300' : 'text-zinc-600'}`}>
                            <p>{faq.answer}</p>
                            {faq.sourceUrl && (
                              <a
                                href={faq.sourceUrl}
                                target="_blank"
                                rel="noreferrer"
                                className={`self-start text-sm font-medium transition-colors ${
                                  isDark ? 'text-nk-official hover:text-nk-official' : 'text-nk-official-dim hover:text-nk-official-dim'
                                }`}
                              >
                                {SOURCE_LABEL[locale] ?? SOURCE_LABEL.en}
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            ))}

            <div className="flex flex-col items-center gap-4 pt-8 text-center">
              <p className={isDark ? 'text-zinc-400' : 'text-zinc-500'}>{locale === 'zh' ? '还有问题？' : locale === 'en' ? 'Still have questions?' : 'Masih ada soalan?'}</p>
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
            <Link href="/about" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-zinc-900'}`}>{t('nav.about')}</Link>
            <Link href="/privacy" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-zinc-900'}`}>{t('footer.privacy')}</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
