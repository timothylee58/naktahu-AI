'use client';

import type { ReactNode } from 'react';
import { LandingHeader } from '@/components/layout/LandingHeader';
import { LandingFooter } from '@/components/landing/LandingFooter';
import { useI18n } from '@/lib/i18n';
import { LANDING_TAGLINE_KEYS } from '@/lib/landing-taglines';
import { useTheme } from '@/lib/theme';

const ISSUES_URL = 'https://github.com/timothylee58/naktahu-AI/issues';
const LAST_REVIEWED = '2026-11-09';

interface StatementContent {
  title: string;
  reviewed: string;
  intro: string;
  goal: { title: string; desc: string };
  features: { title: string; items: string[] };
  limits: { title: string; items: string[] };
  feedback: { title: string; desc: string; link: string };
}

// Long-form per-locale content kept on the page (same pattern as /about)
// rather than in the shared i18n object. Every claim below was checked
// against the codebase — the statement says what is true today, including
// the gaps, instead of asserting a conformance level nobody has audited.
const CONTENT: Record<'ms' | 'en' | 'zh', StatementContent> = {
  ms: {
    title: 'Kenyataan Kebolehcapaian',
    reviewed: 'Kali terakhir disemak',
    intro:
      'NakTahu AI mahu maklumat perkhidmatan awam mudah dicapai oleh semua orang, termasuk pengguna pembaca skrin, papan kekunci sahaja, atau yang sensitif kepada gerakan.',
    goal: {
      title: 'Matlamat kami',
      desc: 'Kami berusaha memenuhi Garis Panduan Kebolehcapaian Kandungan Web (WCAG) 2.2 Tahap AA. Laman ini belum diaudit secara rasmi, jadi kami tidak mendakwa pematuhan penuh.',
    },
    features: {
      title: 'Apa yang telah disediakan',
      items: [
        'Antara muka dalam tiga bahasa (BM, English, 中文), dan bahasa halaman dikemas kini apabila anda menukarnya supaya pembaca skrin menyebut teks dengan betul.',
        'Animasi dikurangkan atau dimatikan apabila tetapan "kurangkan gerakan" peranti anda dihidupkan.',
        'Jawapan yang distrim dan mesej status diumumkan kepada pembaca skrin melalui kawasan langsung (aria-live).',
        'Tema cerah dan gelap, dengan warna teks yang dipilih untuk kontras yang mencukupi.',
        'Penunjuk fokus yang jelas untuk navigasi papan kekunci, dan input suara sebagai alternatif kepada menaip.',
        'Pautan "Langkau ke kandungan utama" sebagai elemen pertama di setiap halaman.',
        'Animasi demo di halaman utama boleh dijeda, dan setiap demo mempunyai penerangan teks untuk pembaca skrin.',
      ],
    },
    limits: {
      title: 'Had yang diketahui',
      items: [
        'Tiada ujian kebolehcapaian automatik dijalankan pada setiap perubahan lagi.',
        'Jawapan AI boleh menjadi panjang; kami sedang menambah baik struktur tajuk dan senarai dalam jawapan.',
        'Lencana pihak ketiga (seperti MakaKami) dimuatkan dari laman luar dan di luar kawalan kami.',
      ],
    },
    feedback: {
      title: 'Maklum balas',
      desc: 'Jika anda menghadapi halangan kebolehcapaian, beritahu kami halaman, peranti dan teknologi bantuan yang anda gunakan. Kami akan mengutamakan pembetulan.',
      link: 'Laporkan isu kebolehcapaian',
    },
  },
  en: {
    title: 'Accessibility Statement',
    reviewed: 'Last reviewed',
    intro:
      'NakTahu AI wants public-service information to be usable by everyone, including people who use screen readers, navigate by keyboard only, or are sensitive to motion.',
    goal: {
      title: 'Our goal',
      desc: 'We aim to meet the Web Content Accessibility Guidelines (WCAG) 2.2 at Level AA. The site has not been formally audited, so we do not claim full conformance.',
    },
    features: {
      title: 'What is in place',
      items: [
        'A three-language interface (BM, English, 中文); the page language updates when you switch, so screen readers pronounce text correctly.',
        'Animations are reduced or turned off when your device’s “reduce motion” setting is on.',
        'Streaming answers and status messages are announced to screen readers through live regions (aria-live).',
        'Light and dark themes, with text colours chosen for sufficient contrast.',
        'Visible focus indicators for keyboard navigation, and voice input as an alternative to typing.',
        'A “Skip to main content” link as the first element on every page.',
        'The demo animations on the home page can be paused, and each demo has a text description for screen readers.',
      ],
    },
    limits: {
      title: 'Known limitations',
      items: [
        'Automated accessibility tests do not yet run on every change.',
        'AI answers can be long; we are improving the heading and list structure inside answers.',
        'Third-party badges (such as MakaKami) load from external sites outside our control.',
      ],
    },
    feedback: {
      title: 'Feedback',
      desc: 'If you hit an accessibility barrier, tell us the page, your device and any assistive technology you use. We will prioritise a fix.',
      link: 'Report an accessibility issue',
    },
  },
  zh: {
    title: '无障碍声明',
    reviewed: '最后审阅日期',
    intro: 'NakTahu AI 希望每个人都能方便地获取公共服务信息，包括使用屏幕阅读器、仅使用键盘浏览或对动态效果敏感的用户。',
    goal: {
      title: '我们的目标',
      desc: '我们致力于达到《网页内容无障碍指南》（WCAG）2.2 AA 级标准。本网站尚未经过正式审核，因此我们不声称完全符合。',
    },
    features: {
      title: '已提供的功能',
      items: [
        '三语界面（BM、English、中文）；切换语言时页面语言会同步更新，让屏幕阅读器正确朗读。',
        '当您的设备开启“减少动态效果”时，动画会减弱或关闭。',
        '实时生成的答案和状态信息会通过实时区域（aria-live）告知屏幕阅读器。',
        '提供浅色和深色主题，文字颜色经过挑选以确保足够的对比度。',
        '键盘导航时有清晰的焦点指示，并支持语音输入代替打字。',
        '每个页面的第一个元素都是“跳到主要内容”链接。',
        '首页的演示动画可以暂停，每个演示都附有供屏幕阅读器使用的文字说明。',
      ],
    },
    limits: {
      title: '已知限制',
      items: [
        '尚未对每次更改运行自动化无障碍测试。',
        'AI 答案可能较长；我们正在改进答案中的标题和列表结构。',
        '第三方徽章（例如 MakaKami）从外部网站加载，不在我们的控制范围内。',
      ],
    },
    feedback: {
      title: '反馈',
      desc: '如果您遇到无障碍障碍，请告诉我们页面、所用设备以及辅助技术。我们会优先修复。',
      link: '报告无障碍问题',
    },
  },
};

export default function AccessibilityPage() {
  const { t, locale } = useI18n();
  const { theme } = useTheme();
  const c = CONTENT[(locale as 'ms' | 'en' | 'zh') in CONTENT ? (locale as 'ms' | 'en' | 'zh') : 'ms'];
  const pageBg = theme === 'dark' ? 'bg-[#12151C]' : 'bg-nk-bg-warm';

  return (
    <div className={`flex min-h-screen flex-col font-sans ${pageBg}`}>
      <LandingHeader />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6 sm:py-16">
        <h1 className="font-display text-3xl font-extrabold tracking-[-0.01em] text-nk-ink sm:text-4xl">{c.title}</h1>
        <p className="mt-2 text-sm text-nk-muted-aa">
          {c.reviewed}: <time dateTime={LAST_REVIEWED}>{LAST_REVIEWED}</time>
        </p>
        <p className="mt-6 text-base leading-relaxed text-nk-ink/80">{c.intro}</p>

        <Block title={c.goal.title}>
          <p>{c.goal.desc}</p>
        </Block>
        <Block title={c.features.title}>
          <List items={c.features.items} />
        </Block>
        <Block title={c.limits.title}>
          <List items={c.limits.items} />
        </Block>
        <Block title={c.feedback.title}>
          <p>{c.feedback.desc}</p>
          <p className="mt-3">
            <a
              href={ISSUES_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-nk-official-text underline underline-offset-2"
            >
              {c.feedback.link} ↗
            </a>
          </p>
        </Block>
      </main>
      <LandingFooter tagline={t(LANDING_TAGLINE_KEYS[0])} />
    </div>
  );
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="font-display text-xl font-bold text-nk-ink sm:text-2xl">{title}</h2>
      <div className="mt-3 text-base leading-relaxed text-nk-ink/80">{children}</div>
    </section>
  );
}

function List({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-2 pl-5">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}
