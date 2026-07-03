'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { UILocale } from '@/lib/types';

type Translations = Record<string, string>;

const MS: Translations = {
  /* ── chat ── */
  'chat.placeholder': 'Taip soalan anda di sini…',
  'chat.send': 'Hantar',
  'chat.mic': 'Input suara',
  'chat.mic_denied': 'Akses mikrofon dinafikan',
  'chat.thinking': 'Sedang berfikir…',
  'chat.warning.low_confidence':
    'Jawapan mungkin tidak tepat / Answer may be inaccurate',
  'chat.language_indicator': 'BM',
  'chat.empty':
    'Tanya saya soalan berkaitan perkhidmatan kerajaan Malaysia.',
  'chat.keyboard_hint': 'Enter untuk hantar · Ctrl+Enter · Esc untuk padam',
  'chat.suggestions_label': 'Anda mungkin ingin tanya',

  /* ── header & nav ── */
  'header.title': 'NakTahu',
  'header.subtitle': 'Soal tentang kerajaan',
  'header.lang_toggle': 'EN',
  'header.history': 'Sejarah',
  'header.menu': 'Menu',
  'header.sign_in': 'Daftar / Masuk',
  'header.register': 'Daftar',
  'header.login': 'Masuk',
  'header.sign_out': 'Keluar',
  'nav.try_question': 'Cuba Tanya',
  'nav.home': 'Beranda',
  'nav.about': 'Tentang Kami',
  'nav.faq': 'Bantuan / FAQ',
  'nav.contact': 'Hubungi Kami',
  'nav.pricing': 'Harga',
  'sidebar.collapse': 'Lipat panel',
  'sidebar.expand': 'Buka panel',

  /* ── pricing ── */
  'pricing.title': 'Pilih pelan anda',
  'pricing.subtitle': 'Mula percuma. Naik taraf bila-bila masa.',
  'pricing.free.name': 'Percuma',
  'pricing.free.price': 'RM 0',
  'pricing.free.period': '/bulan',
  'pricing.free.cta': 'Pelan semasa anda',
  'pricing.free.feature.1': '20 soalan sehari',
  'pricing.free.feature.2': 'Semua 6 domain RAG',
  'pricing.free.feature.3': 'BM + EN dengan sumber rujukan',
  'pricing.pro.name': 'Pro — Individu',
  'pricing.pro.price': 'RM 19',
  'pricing.pro.period': '/bulan',
  'pricing.pro.cta': 'Langgani',
  'pricing.pro.feature.1': 'Soalan tanpa had',
  'pricing.pro.feature.2': 'Input suara (ms-MY)',
  'pricing.pro.feature.3': 'Sejarah 30 hari + eksport PDF',
  'pricing.pro.feature.4': 'Ejen Pemantau Tarikh Akhir',
  'pricing.business.name': 'Pro — Perniagaan',
  'pricing.business.price': 'RM 99',
  'pricing.business.period': '/bulan setiap ruang kerja',
  'pricing.business.cta': 'Langgani',
  'pricing.business.feature.1': 'Semua ciri Pro',
  'pricing.business.feature.2': '5 tempat pasukan',
  'pricing.business.feature.3': 'Sejarah dikongsi',
  'pricing.business.feature.4': '1,000 panggilan API/bulan',
  'pricing.student.name': 'Pelajar',
  'pricing.student.price': 'RM 29',
  'pricing.student.period': '/bulan',
  'pricing.student.cta': 'Langgani',
  'pricing.student.desc': 'Ejen Kajian untuk pelajar SPM/STPM — muat naik PDF, penjejakan topik.',
  'pricing.credits.title': 'Kredit Ejen',
  'pricing.credits.subtitle': 'RM 5 sekredit — digunakan untuk laporan Ejen Pematuhan, konsultasi Imigresen.',
  'pricing.credits.buy': 'Beli',
  'pricing.signin_required': 'Sila daftar masuk untuk melanggan',
  'pricing.processing': 'Memproses…',
  'pricing.error': 'Sesuatu tidak kena. Sila cuba lagi.',

  /* ── language picker ── */
  'lang.ms': 'Bahasa Malaysia',
  'lang.en': 'English',
  'lang.zh': '中文',
  'lang.label': 'Bahasa',

  /* ── auth modal ── */
  'auth.modal.title': 'Masuk ke NakTahu',
  'auth.modal.subtitle': 'Simpan sejarah soalan anda',
  'auth.google': 'Teruskan dengan Google',
  'auth.google.loading': 'Menghubungi Google…',
  'auth.or': 'atau',
  'auth.email': 'Teruskan dengan Emel',
  'auth.email.placeholder': 'nama@emel.com',
  'auth.email.send': 'Hantar pautan log masuk',
  'auth.email.sending': 'Menghantar…',
  'auth.email.sent.title': 'Semak emel anda',
  'auth.email.sent.desc': 'Pautan log masuk dihantar ke',
  'auth.email.back': 'Kembali',
  'auth.terms': 'Dengan log masuk, anda bersetuju dengan',
  'auth.terms.link': 'terma penggunaan',
  'auth.microsoft': 'Teruskan dengan Microsoft',
  'auth.microsoft.loading': 'Menghubungi Microsoft…',
  'auth.error.title': 'Log masuk gagal',
  'auth.error.generic': 'Tidak dapat melengkapkan log masuk. Sila cuba lagi.',
  'auth.error.access_denied': 'Log masuk dibatalkan. Sila cuba lagi jika anda ingin meneruskan.',
  'auth.error.dismiss': 'Tutup',

  /* ── history ── */
  'history.title': 'Sejarah Soalan',
  'history.empty': 'Tiada sejarah lagi.',
  'history.sign_in_prompt': 'Daftar masuk untuk simpan sejarah soalan anda.',
  'history.group.today': 'Hari ini',
  'history.group.yesterday': 'Semalam',
  'history.group.earlier': 'Sebelum ini',

  /* ── landing ── */
  'landing.badge': 'Dibuat untuk Malaysia',
  'landing.hero.headline': 'Tanya apa sahaja tentang Malaysia.',
  'landing.hero.headline.highlight': 'Malaysia',
  'landing.hero.subtext':
    'NakTahu AI memberi jawapan berdasarkan sumber rasmi kerajaan.',
  'landing.hero.cta': 'Mula Bertanya',
  'landing.features.title': 'Kenapa NakTahu?',
  'landing.features.bilingual.title': 'Tiga Bahasa',
  'landing.features.bilingual.desc':
    'Tanya dalam BM, Inggeris atau Mandarin — jawapan tepat dalam ketiga-tiga bahasa.',
  'landing.features.cited.title': 'Sumber Disahkan',
  'landing.features.cited.desc':
    'Setiap jawapan disertakan pautan ke dokumen rasmi kerajaan.',
  'landing.features.voice.title': 'Input Suara',
  'landing.features.voice.desc':
    'Sebut soalan anda — teknologi pengecaman suara terbina dalam.',
  'landing.domains.title': 'Domain Pengetahuan',
  'landing.footer.tagline': 'Maklumat kerajaan, dalam genggaman anda.',
  'landing.footer.disclaimer':
    'NakTahu AI adalah projek portfolio. Bukan nasihat rasmi kerajaan.',
  'landing.footer.github': 'GitHub',

  /* ── domains ── */
  'domain.tax': 'Cukai & LHDN',
  'domain.epf': 'KWSP / EPF',
  'domain.business': 'Perniagaan & SSM',
  'domain.education': 'Pendidikan & SPM',
  'domain.health': 'Kesihatan',
  'domain.immigration': 'Imigresen',

  /* ── career wizard ── */
  'career.badge': 'Perancang Kerjaya',
  'career.hero.title': 'Rancang laluan kerjaya anda',
  'career.hero.sub': 'Jawab 3 soalan ringkas — dapatkan pelan tindakan peribadi.',
  'career.step': 'Langkah',
  'career.of': 'daripada',
  'career.back': 'Kembali',
  'career.next': 'Seterusnya',
  'career.generate': 'Jana Pelan Kerjaya',
  'career.s1.title': 'Apakah latar belakang anda?',
  'career.s1.edu': 'Tahap Pendidikan',
  'career.s1.field': 'Bidang Semasa',
  'career.s1.status': 'Status Kewarganegaraan',
  'career.s2.title': 'Apakah matlamat anda?',
  'career.s2.goal': 'Sasaran Kerjaya',
  'career.s2.timeline': 'Jangka Masa',
  'career.s3.title': 'Butiran tambahan',
  'career.s3.state': 'Negeri',
  'career.s3.lang': 'Bahasa Pilihan',

  /* ── errors ── */
  'error.stream': 'Ralat semasa mendapatkan jawapan. Cuba lagi.',
  'error.voice_unsupported':
    'Pengecaman suara tidak disokong oleh pelayar ini.',
  'error.history_fetch': 'Gagal memuatkan sejarah. Cuba lagi.',
  'error.retry': 'Cuba Lagi',

  /* ── footer ── */
  'footer.privacy': 'Dasar Privasi',
};

const EN: Translations = {
  /* ── chat ── */
  'chat.placeholder': 'Type your question here…',
  'chat.send': 'Send',
  'chat.mic': 'Voice input',
  'chat.mic_denied': 'Microphone access denied',
  'chat.thinking': 'Thinking…',
  'chat.warning.low_confidence':
    'Jawapan mungkin tidak tepat / Answer may be inaccurate',
  'chat.language_indicator': 'EN',
  'chat.empty': 'Ask me anything about Malaysian government services.',
  'chat.keyboard_hint': 'Enter to send · Ctrl+Enter · Esc to clear',
  'chat.suggestions_label': 'You might also ask',

  /* ── header & nav ── */
  'header.title': 'NakTahu',
  'header.subtitle': 'Ask about government',
  'header.lang_toggle': 'BM',
  'header.history': 'History',
  'header.menu': 'Menu',
  'header.sign_in': 'Register / Login',
  'header.register': 'Register',
  'header.login': 'Login',
  'header.sign_out': 'Sign Out',
  'nav.try_question': 'Try a Question',
  'nav.home': 'Home',
  'nav.about': 'About Us',
  'nav.faq': 'Help / FAQ',
  'nav.contact': 'Contact Us',
  'nav.pricing': 'Pricing',
  'sidebar.collapse': 'Collapse sidebar',
  'sidebar.expand': 'Expand sidebar',

  /* ── pricing ── */
  'pricing.title': 'Choose your plan',
  'pricing.subtitle': 'Start free. Upgrade any time.',
  'pricing.free.name': 'Free',
  'pricing.free.price': 'RM 0',
  'pricing.free.period': '/mo',
  'pricing.free.cta': 'Your current plan',
  'pricing.free.feature.1': '20 queries per day',
  'pricing.free.feature.2': 'All 6 RAG domains',
  'pricing.free.feature.3': 'BM + EN with source citations',
  'pricing.pro.name': 'Pro — Individual',
  'pricing.pro.price': 'RM 19',
  'pricing.pro.period': '/mo',
  'pricing.pro.cta': 'Subscribe',
  'pricing.pro.feature.1': 'Unlimited queries',
  'pricing.pro.feature.2': 'Voice input (ms-MY)',
  'pricing.pro.feature.3': '30-day history + PDF export',
  'pricing.pro.feature.4': 'Deadline Monitor agent',
  'pricing.business.name': 'Pro — Business',
  'pricing.business.price': 'RM 99',
  'pricing.business.period': '/mo per workspace',
  'pricing.business.cta': 'Subscribe',
  'pricing.business.feature.1': 'Everything in Pro',
  'pricing.business.feature.2': '5 team seats',
  'pricing.business.feature.3': 'Shared history',
  'pricing.business.feature.4': '1,000 API calls/mo',
  'pricing.student.name': 'Student',
  'pricing.student.price': 'RM 29',
  'pricing.student.period': '/mo',
  'pricing.student.cta': 'Subscribe',
  'pricing.student.desc': 'Study Agent for SPM/STPM students — PDF upload, topic tracking.',
  'pricing.credits.title': 'Agent Credits',
  'pricing.credits.subtitle': 'RM 5 per credit — spent on Compliance Drafter reports, Immigration consults.',
  'pricing.credits.buy': 'Buy',
  'pricing.signin_required': 'Sign in to subscribe',
  'pricing.processing': 'Processing…',
  'pricing.error': 'Something went wrong. Please try again.',

  /* ── language picker ── */
  'lang.ms': 'Bahasa Malaysia',
  'lang.en': 'English',
  'lang.zh': '中文',
  'lang.label': 'Language',

  /* ── auth modal ── */
  'auth.modal.title': 'Sign in to NakTahu',
  'auth.modal.subtitle': 'Save your question history',
  'auth.google': 'Continue with Google',
  'auth.google.loading': 'Connecting to Google…',
  'auth.or': 'or',
  'auth.email': 'Continue with Email',
  'auth.email.placeholder': 'name@email.com',
  'auth.email.send': 'Send login link',
  'auth.email.sending': 'Sending…',
  'auth.email.sent.title': 'Check your email',
  'auth.email.sent.desc': 'Login link sent to',
  'auth.email.back': 'Back',
  'auth.terms': 'By signing in, you agree to our',
  'auth.terms.link': 'terms of use',
  'auth.microsoft': 'Continue with Microsoft',
  'auth.microsoft.loading': 'Connecting to Microsoft…',
  'auth.error.title': 'Sign-in failed',
  'auth.error.generic': 'Could not complete sign-in. Please try again.',
  'auth.error.access_denied': 'Sign-in was cancelled. Try again if you want to continue.',
  'auth.error.dismiss': 'Dismiss',

  /* ── history ── */
  'history.title': 'Query History',
  'history.empty': 'No history yet.',
  'history.sign_in_prompt': 'Sign in to save your query history.',
  'history.group.today': 'Today',
  'history.group.yesterday': 'Yesterday',
  'history.group.earlier': 'Earlier',

  /* ── landing ── */
  'landing.badge': 'Built for Malaysia',
  'landing.hero.headline': 'Ask anything about Malaysia.',
  'landing.hero.headline.highlight': 'Malaysia',
  'landing.hero.subtext':
    'NakTahu AI provides answers grounded in official government sources.',
  'landing.hero.cta': 'Start Asking',
  'landing.features.title': 'Why NakTahu?',
  'landing.features.bilingual.title': 'Trilingual BM · EN · 中文',
  'landing.features.bilingual.desc':
    'Ask in Bahasa Malaysia, English, or Mandarin — accurate answers in all three.',
  'landing.features.cited.title': 'Verified Sources',
  'landing.features.cited.desc':
    'Every answer links back to official government documents.',
  'landing.features.voice.title': 'Voice Input',
  'landing.features.voice.desc':
    'Speak your question — speech recognition built right in.',
  'landing.domains.title': 'Knowledge Domains',
  'landing.footer.tagline': 'Government information, at your fingertips.',
  'landing.footer.disclaimer':
    'NakTahu AI is a portfolio project. Not official government advice.',
  'landing.footer.github': 'GitHub',

  /* ── domains ── */
  'domain.tax': 'Tax & LHDN',
  'domain.epf': 'EPF / KWSP',
  'domain.business': 'Business & SSM',
  'domain.education': 'Education & SPM',
  'domain.health': 'Healthcare',
  'domain.immigration': 'Immigration',

  /* ── career wizard ── */
  'career.badge': 'Career Planner',
  'career.hero.title': 'Plan your career path',
  'career.hero.sub': 'Answer 3 quick questions — get a personalised action plan.',
  'career.step': 'Step',
  'career.of': 'of',
  'career.back': 'Back',
  'career.next': 'Next',
  'career.generate': 'Generate Career Plan',
  'career.s1.title': 'What is your background?',
  'career.s1.edu': 'Education Level',
  'career.s1.field': 'Current Field',
  'career.s1.status': 'Citizenship Status',
  'career.s2.title': 'What is your goal?',
  'career.s2.goal': 'Career Target',
  'career.s2.timeline': 'Timeline',
  'career.s3.title': 'A few more details',
  'career.s3.state': 'State',
  'career.s3.lang': 'Preferred Language',

  /* ── errors ── */
  'error.stream': 'Error fetching answer. Please try again.',
  'error.voice_unsupported':
    'Speech recognition is not supported in this browser.',
  'error.history_fetch': 'Failed to load history. Please try again.',
  'error.retry': 'Try Again',

  /* ── footer ── */
  'footer.privacy': 'Privacy Policy',
};

const ZH: Translations = {
  /* ── chat ── */
  'chat.placeholder': '在此输入您的问题…',
  'chat.send': '发送',
  'chat.mic': '语音输入',
  'chat.mic_denied': '麦克风访问被拒绝',
  'chat.thinking': '思考中…',
  'chat.warning.low_confidence': '答案可能不准确 / Answer may be inaccurate',
  'chat.language_indicator': '中文',
  'chat.empty': '请向我询问有关马来西亚政府服务的问题。',
  'chat.keyboard_hint': '按 Enter 发送 · Ctrl+Enter · Esc 清空',
  'chat.suggestions_label': '您可能还想问',

  /* ── header & nav ── */
  'header.title': 'NakTahu',
  'header.subtitle': '询问政府事务',
  'header.lang_toggle': 'BM',
  'header.history': '历史记录',
  'header.menu': '菜单',
  'header.sign_in': '注册登录',
  'header.register': '注册',
  'header.login': '登录',
  'header.sign_out': '退出',
  'nav.try_question': '尝试提问',
  'nav.home': '首页',
  'nav.about': '关于我们',
  'nav.faq': '帮助 / 常见问题',
  'nav.contact': '联系我们',
  'nav.pricing': '价格',
  'sidebar.collapse': '收起侧栏',
  'sidebar.expand': '展开侧栏',

  /* ── pricing ── */
  'pricing.title': '选择您的套餐',
  'pricing.subtitle': '免费开始，随时升级。',
  'pricing.free.name': '免费版',
  'pricing.free.price': 'RM 0',
  'pricing.free.period': '/月',
  'pricing.free.cta': '您当前的套餐',
  'pricing.free.feature.1': '每日 20 次查询',
  'pricing.free.feature.2': '全部 6 个知识领域',
  'pricing.free.feature.3': '马来文 + 英文，附来源引用',
  'pricing.pro.name': 'Pro — 个人版',
  'pricing.pro.price': 'RM 19',
  'pricing.pro.period': '/月',
  'pricing.pro.cta': '订阅',
  'pricing.pro.feature.1': '无限次查询',
  'pricing.pro.feature.2': '语音输入 (ms-MY)',
  'pricing.pro.feature.3': '30 天历史记录 + PDF 导出',
  'pricing.pro.feature.4': '截止日期监控代理',
  'pricing.business.name': 'Pro — 商业版',
  'pricing.business.price': 'RM 99',
  'pricing.business.period': '/月，每个工作区',
  'pricing.business.cta': '订阅',
  'pricing.business.feature.1': '包含 Pro 所有功能',
  'pricing.business.feature.2': '5 个团队席位',
  'pricing.business.feature.3': '共享历史记录',
  'pricing.business.feature.4': '每月 1,000 次 API 调用',
  'pricing.student.name': '学生版',
  'pricing.student.price': 'RM 29',
  'pricing.student.period': '/月',
  'pricing.student.cta': '订阅',
  'pricing.student.desc': '面向 SPM/STPM 学生的学习代理 — PDF 上传、主题追踪。',
  'pricing.credits.title': '代理点数',
  'pricing.credits.subtitle': '每点数 RM 5 — 用于合规起草代理报告、移民咨询。',
  'pricing.credits.buy': '购买',
  'pricing.signin_required': '请登录以订阅',
  'pricing.processing': '处理中…',
  'pricing.error': '出了点问题，请重试。',

  /* ── language picker ── */
  'lang.ms': 'Bahasa Malaysia',
  'lang.en': 'English',
  'lang.zh': '中文',
  'lang.label': '语言',

  /* ── auth modal ── */
  'auth.modal.title': '登录 NakTahu',
  'auth.modal.subtitle': '保存您的问题历史',
  'auth.google': 'Google 登录',
  'auth.google.loading': '连接 Google…',
  'auth.or': '或',
  'auth.email': '邮箱登录',
  'auth.email.placeholder': 'name@email.com',
  'auth.email.send': '发送登录链接',
  'auth.email.sending': '发送中…',
  'auth.email.sent.title': '请查看您的电子邮件',
  'auth.email.sent.desc': '登录链接已发送至',
  'auth.email.back': '返回',
  'auth.terms': '登录即表示您同意我们的',
  'auth.terms.link': '使用条款',
  'auth.microsoft': 'Microsoft 登录',
  'auth.microsoft.loading': '连接 Microsoft…',
  'auth.error.title': '登录失败',
  'auth.error.generic': '无法完成登录，请重试。',
  'auth.error.access_denied': '登录已取消。如需继续，请重试。',
  'auth.error.dismiss': '关闭',

  /* ── history ── */
  'history.title': '查询历史',
  'history.empty': '暂无历史记录。',
  'history.sign_in_prompt': '登录以保存您的查询历史。',
  'history.group.today': '今天',
  'history.group.yesterday': '昨天',
  'history.group.earlier': '更早',

  /* ── landing ── */
  'landing.badge': '专为马来西亚打造',
  'landing.hero.headline': '关于马来西亚政策，尽管问',
  'landing.hero.headline.highlight': '马来西亚',
  'landing.hero.subtext': 'NakTahu AI 提供基于官方政府来源的答案。',
  'landing.hero.cta': '开始提问',
  'landing.features.title': '为什么选择 NakTahu？',
  'landing.features.bilingual.title': '三语 BM·EN·中文',
  'landing.features.bilingual.desc': '以马来语、英语或中文提问，均可获得准确答案。',
  'landing.features.cited.title': '经过验证的来源',
  'landing.features.cited.desc': '每个答案都链接到官方政府文件。',
  'landing.features.voice.title': '语音输入',
  'landing.features.voice.desc': '说出您的问题，内置语音识别功能。',
  'landing.domains.title': '知识领域',
  'landing.footer.tagline': '政府信息，触手可及。',
  'landing.footer.disclaimer': 'NakTahu AI 是一个作品集项目，不代表官方政府建议。',
  'landing.footer.github': 'GitHub',

  /* ── domains ── */
  'domain.tax': '税务与国内税收局',
  'domain.epf': '雇员公积金',
  'domain.business': '商业与公司委员会',
  'domain.education': '教育与大马教育文凭',
  'domain.health': '医疗卫生',
  'domain.immigration': '移民事务',

  /* ── career wizard ── */
  'career.badge': '职业规划',
  'career.hero.title': '规划您的职业道路',
  'career.hero.sub': '回答3个简短问题，获取个性化行动计划。',
  'career.step': '第',
  'career.of': '步，共',
  'career.back': '返回',
  'career.next': '下一步',
  'career.generate': '生成职业计划',
  'career.s1.title': '您的背景是什么？',
  'career.s1.edu': '教育程度',
  'career.s1.field': '当前领域',
  'career.s1.status': '公民身份',
  'career.s2.title': '您的目标是什么？',
  'career.s2.goal': '职业目标',
  'career.s2.timeline': '时间线',
  'career.s3.title': '更多详情',
  'career.s3.state': '州属',
  'career.s3.lang': '首选语言',

  /* ── errors ── */
  'error.stream': '获取答案时出错，请重试。',
  'error.voice_unsupported': '此浏览器不支持语音识别。',
  'error.history_fetch': '加载历史记录失败，请重试。',
  'error.retry': '重试',

  /* ── footer ── */
  'footer.privacy': '隐私政策',
};

const DICTS: Record<UILocale, Translations> = { ms: MS, en: EN, zh: ZH };

const STORAGE_KEY = 'naktahu_locale';

function readStoredLocale(): UILocale {
  if (typeof window === 'undefined') return 'ms';
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === 'ms' || v === 'en' || v === 'zh') return v;
  return 'ms';
}

interface I18nContextValue {
  locale: UILocale;
  setLocale: (l: UILocale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue>({
  locale: 'ms',
  setLocale: () => undefined,
  t: (k) => k,
});

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<UILocale>('ms');

  // Hydrate from localStorage after mount (avoids SSR mismatch)
  useEffect(() => {
    const stored = readStoredLocale();
    setLocaleState(stored);
    document.documentElement.lang = stored === 'zh' ? 'zh-Hans' : stored;
  }, []);

  const setLocale = useCallback((l: UILocale) => {
    localStorage.setItem(STORAGE_KEY, l);
    setLocaleState(l);
    document.documentElement.lang = l === 'zh' ? 'zh-Hans' : l;
  }, []);

  const t = useCallback(
    (key: string) => DICTS[locale][key] ?? key,
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
