'use client';

import { useI18n } from '@/lib/i18n';

interface Chip {
  labelMs: string;
  labelEn: string;
  labelZh: string;
  queryMs: string;
  queryEn: string;
  queryZh: string;
}

const CHIPS: Chip[] = [
  {
    labelMs: 'Cara bayar cukai',
    labelEn: 'How to pay taxes',
    labelZh: '如何缴税',
    queryMs: 'Bagaimana cara untuk membayar cukai pendapatan di Malaysia?',
    queryEn: 'How do I pay income tax in Malaysia?',
    queryZh: '在马来西亚如何缴纳所得税？',
  },
  {
    labelMs: 'Pengeluaran KWSP',
    labelEn: 'EPF withdrawal',
    labelZh: '公积金提款',
    queryMs: 'Bagaimana cara mengeluarkan wang KWSP untuk pembelian rumah pertama?',
    queryEn: 'How do I withdraw EPF for first home purchase?',
    queryZh: '如何提取公积金用于购买首套房屋？',
  },
  {
    labelMs: 'Daftar syarikat',
    labelEn: 'Register a company',
    labelZh: '注册公司',
    queryMs: 'Apakah langkah-langkah untuk mendaftarkan syarikat di SSM Malaysia?',
    queryEn: 'What are the steps to register a company with SSM Malaysia?',
    queryZh: '在马来西亚SSM注册公司的步骤是什么？',
  },
  {
    labelMs: 'MyKad hilang',
    labelEn: 'Lost MyKad',
    labelZh: '遗失身份证',
    queryMs: 'Apa yang perlu dilakukan jika MyKad hilang?',
    queryEn: 'What should I do if I lose my MyKad?',
    queryZh: '如果我的身份证遗失了该怎么办？',
  },
  {
    labelMs: 'Visa kerja',
    labelEn: 'Work visa',
    labelZh: '工作签证',
    queryMs: 'Bagaimana cara memohon permit kerja atau pas pekerjaan di Malaysia?',
    queryEn: 'How do I apply for a work permit in Malaysia?',
    queryZh: '如何在马来西亚申请工作准证？',
  },
  {
    labelMs: 'Bantuan pelajaran',
    labelEn: 'Education aid',
    labelZh: '教育资助',
    queryMs: 'Apakah bantuan kewangan yang tersedia untuk pelajar universiti di Malaysia?',
    queryEn: 'What financial aid is available for university students in Malaysia?',
    queryZh: '马来西亚大学生有哪些经济援助可以申请？',
  },
];

interface PromptChipsProps {
  onSelect: (query: string) => void;
  disabled?: boolean;
  variant?: 'light' | 'dark';
}

export function PromptChips({ onSelect, disabled, variant = 'light' }: PromptChipsProps) {
  const { locale } = useI18n();
  const isDark = variant === 'dark';
  const chipClass = isDark
    ? 'bg-white/5 hover:bg-blue-500/20 hover:text-blue-300 hover:border-blue-500/40 text-zinc-300 border-white/10'
    : 'bg-zinc-100 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200 text-zinc-600 border-zinc-200';

  const getLabel = (chip: Chip) => {
    if (locale === 'zh') return chip.labelZh;
    if (locale === 'ms') return chip.labelMs;
    return chip.labelEn;
  };

  const getQuery = (chip: Chip) => {
    if (locale === 'zh') return chip.queryZh;
    if (locale === 'ms') return chip.queryMs;
    return chip.queryEn;
  };

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {CHIPS.map((chip) => (
        <button
          key={chip.labelEn}
          onClick={() => onSelect(getQuery(chip))}
          disabled={disabled}
          className={`flex-shrink-0 px-3 py-1.5 border rounded-full text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap ${chipClass}`}
        >
          {getLabel(chip)}
        </button>
      ))}
    </div>
  );
}
