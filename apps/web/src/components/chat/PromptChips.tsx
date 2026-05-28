'use client';

import { useI18n } from '@/lib/i18n';

interface Chip {
  labelMs: string;
  labelEn: string;
  query: string;
}

const CHIPS: Chip[] = [
  { labelMs: 'Cara bayar cukai', labelEn: 'How to pay taxes', query: 'Bagaimana cara untuk membayar cukai pendapatan di Malaysia?' },
  { labelMs: 'Pengeluaran KWSP', labelEn: 'EPF withdrawal', query: 'Bagaimana cara mengeluarkan wang KWSP untuk pembelian rumah pertama?' },
  { labelMs: 'Daftar syarikat', labelEn: 'Register a company', query: 'Apakah langkah-langkah untuk mendaftarkan syarikat di SSM Malaysia?' },
  { labelMs: 'MyKad hilang', labelEn: 'Lost MyKad', query: 'Apa yang perlu dilakukan jika MyKad hilang?' },
  { labelMs: 'Visa kerja', labelEn: 'Work visa', query: 'Bagaimana cara memohon permit kerja atau pas pekerjaan di Malaysia?' },
  { labelMs: 'Bantuan pelajaran', labelEn: 'Education aid', query: 'Apakah bantuan kewangan yang tersedia untuk pelajar universiti di Malaysia?' },
];

interface PromptChipsProps {
  onSelect: (query: string) => void;
  disabled?: boolean;
}

export function PromptChips({ onSelect, disabled }: PromptChipsProps) {
  const { locale } = useI18n();
  const isMs = locale === 'ms';

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {CHIPS.map((chip) => (
        <button
          key={chip.query}
          onClick={() => onSelect(chip.query)}
          disabled={disabled}
          className="flex-shrink-0 px-3 py-1.5 bg-zinc-100 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200 text-zinc-600 border border-zinc-200 rounded-full text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
        >
          {isMs ? chip.labelMs : chip.labelEn}
        </button>
      ))}
    </div>
  );
}
