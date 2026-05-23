'use client';

import {
  createContext,
  useCallback,
  useContext,
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
  'chat.thinking': 'Sedang berfikir…',
  'chat.warning.low_confidence':
    'Jawapan mungkin tidak tepat / Answer may be inaccurate',
  'chat.language_indicator': 'BM',
  'chat.empty':
    'Tanya saya soalan berkaitan perkhidmatan kerajaan Malaysia.',

  /* ── header ── */
  'header.title': 'NakTahu',
  'header.subtitle': 'Soal tentang kerajaan',
  'header.lang_toggle': 'EN',
  'header.history': 'Sejarah',
  'header.sign_in': 'Daftar Masuk',
  'header.sign_out': 'Keluar',

  /* ── history ── */
  'history.title': 'Sejarah Soalan',
  'history.empty': 'Tiada sejarah lagi.',
  'history.sign_in_prompt': 'Daftar masuk untuk simpan sejarah soalan anda.',
  'history.group.today': 'Hari ini',
  'history.group.yesterday': 'Semalam',
  'history.group.earlier': 'Sebelum ini',

  /* ── landing ── */
  'landing.hero.headline': 'Tanya apa sahaja tentang Malaysia.',
  'landing.hero.subtext':
    'NakTahu AI memberi jawapan berdasarkan sumber rasmi kerajaan.',
  'landing.hero.cta': 'Mula Bertanya',
  'landing.features.title': 'Kenapa NakTahu?',
  'landing.features.bilingual.title': 'Dwibahasa BM & EN',
  'landing.features.bilingual.desc':
    'Tanya dalam Bahasa Malaysia atau Inggeris — jawapan tepat dalam kedua-dua bahasa.',
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

  /* ── errors ── */
  'error.stream': 'Ralat semasa mendapatkan jawapan. Cuba lagi.',
  'error.voice_unsupported':
    'Pengecaman suara tidak disokong oleh pelayar ini.',
};

const EN: Translations = {
  /* ── chat ── */
  'chat.placeholder': 'Type your question here…',
  'chat.send': 'Send',
  'chat.mic': 'Voice input',
  'chat.thinking': 'Thinking…',
  'chat.warning.low_confidence':
    'Jawapan mungkin tidak tepat / Answer may be inaccurate',
  'chat.language_indicator': 'EN',
  'chat.empty': 'Ask me anything about Malaysian government services.',

  /* ── header ── */
  'header.title': 'NakTahu',
  'header.subtitle': 'Ask about government',
  'header.lang_toggle': 'BM',
  'header.history': 'History',
  'header.sign_in': 'Sign In',
  'header.sign_out': 'Sign Out',

  /* ── history ── */
  'history.title': 'Query History',
  'history.empty': 'No history yet.',
  'history.sign_in_prompt': 'Sign in to save your query history.',
  'history.group.today': 'Today',
  'history.group.yesterday': 'Yesterday',
  'history.group.earlier': 'Earlier',

  /* ── landing ── */
  'landing.hero.headline': 'Ask anything about Malaysia.',
  'landing.hero.subtext':
    'NakTahu AI provides answers grounded in official government sources.',
  'landing.hero.cta': 'Start Asking',
  'landing.features.title': 'Why NakTahu?',
  'landing.features.bilingual.title': 'Bilingual BM & EN',
  'landing.features.bilingual.desc':
    'Ask in Bahasa Malaysia or English — accurate answers in both.',
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

  /* ── errors ── */
  'error.stream': 'Error fetching answer. Please try again.',
  'error.voice_unsupported':
    'Speech recognition is not supported in this browser.',
};

const DICTS: Record<UILocale, Translations> = { ms: MS, en: EN };

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
  const [locale, setLocale] = useState<UILocale>('ms');

  const t = useCallback(
    (key: string) => DICTS[locale][key] ?? key,
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
