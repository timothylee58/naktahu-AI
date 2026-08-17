'use client';

import Link from 'next/link';
import { useI18n } from '@/lib/i18n';
import { matchAgentRules, type AgentSuggestion } from '@/lib/agent-suggestions';

interface Chip {
  labelMs: string;
  labelEn: string;
  labelZh: string;
  queryMs: string;
  queryEn: string;
  queryZh: string;
}

interface ChipGroup {
  /** i18n key for the group header ("Tax & EPF", etc). */
  titleKey: string;
  chips: Chip[];
}

// Same 10 example queries as before, regrouped into 4 domain clusters
// instead of one flat 10-item row (Chunking rule: ≤4 per group). Grouping
// mirrors the domains these queries actually route to via matchAgentRules
// below, not an arbitrary taxonomy.
const GROUPS: ChipGroup[] = [
  {
    titleKey: 'chat.groups.tax_epf',
    chips: [
      {
        labelMs: 'Cara bayar cukai', labelEn: 'How to pay taxes', labelZh: '如何缴税',
        queryMs: 'Bagaimana cara untuk membayar cukai pendapatan di Malaysia?',
        queryEn: 'How do I pay income tax in Malaysia?',
        queryZh: '在马来西亚如何缴纳所得税？',
      },
      {
        labelMs: 'Pengeluaran KWSP', labelEn: 'EPF withdrawal', labelZh: '公积金提款',
        queryMs: 'Bagaimana cara mengeluarkan wang KWSP untuk pembelian rumah pertama?',
        queryEn: 'How do I withdraw EPF for first home purchase?',
        queryZh: '如何提取公积金用于购买首套房屋？',
      },
    ],
  },
  {
    titleKey: 'chat.groups.business_grants',
    chips: [
      {
        labelMs: 'Daftar syarikat', labelEn: 'Register a company', labelZh: '注册公司',
        queryMs: 'Apakah langkah-langkah untuk mendaftarkan syarikat di SSM Malaysia?',
        queryEn: 'What are the steps to register a company with SSM Malaysia?',
        queryZh: '在马来西亚SSM注册公司的步骤是什么？',
      },
      {
        labelMs: 'Geran perniagaan', labelEn: 'Grants I qualify for', labelZh: '符合资格的资助',
        queryMs: 'Apakah geran kerajaan yang saya layak mohon sebagai pemilik perniagaan kecil?',
        queryEn: 'What grants am I eligible for as a small business owner?',
        queryZh: '作为小型企业主，我可以申请哪些政府资助？',
      },
      {
        labelMs: 'Gabung geran', labelEn: 'Combine grants', labelZh: '资助叠加',
        queryMs: 'Bolehkah saya memohon dua geran kerajaan yang berbeza pada masa yang sama?',
        queryEn: 'Can I apply for two different government grants at the same time?',
        queryZh: '我可以同时申请两项不同的政府资助吗？',
      },
      {
        labelMs: 'Tarikh tutup geran', labelEn: 'Grant deadline alerts', labelZh: '资助截止提醒',
        queryMs: 'Bila tarikh tutup permohonan geran ini dan bagaimana saya boleh dapat peringatan?',
        queryEn: "When does this grant's application window close, and how do I get a reminder?",
        queryZh: '这项资助的申请截止日期是什么时候？我该如何收到提醒？',
      },
    ],
  },
  {
    titleKey: 'chat.groups.immigration_docs',
    chips: [
      {
        labelMs: 'MyKad hilang', labelEn: 'Lost MyKad', labelZh: '遗失身份证',
        queryMs: 'Apa yang perlu dilakukan jika MyKad hilang?',
        queryEn: 'What should I do if I lose my MyKad?',
        queryZh: '如果我的身份证遗失了该怎么办？',
      },
      {
        labelMs: 'Visa kerja', labelEn: 'Work visa', labelZh: '工作签证',
        queryMs: 'Bagaimana cara memohon permit kerja atau pas pekerjaan di Malaysia?',
        queryEn: 'How do I apply for a work permit in Malaysia?',
        queryZh: '如何在马来西亚申请工作准证？',
      },
    ],
  },
  {
    titleKey: 'chat.groups.civic_education',
    chips: [
      {
        labelMs: 'Bantuan pelajaran', labelEn: 'Education aid', labelZh: '教育资助',
        queryMs: 'Apakah bantuan kewangan yang tersedia untuk pelajar universiti di Malaysia?',
        queryEn: 'What financial aid is available for university students in Malaysia?',
        queryZh: '马来西亚大学生有哪些经济援助可以申请？',
      },
      {
        labelMs: 'Wakil parlimen', labelEn: 'My MP', labelZh: '我的议员',
        queryMs: 'Siapakah ahli parlimen bagi kawasan saya dan bagaimana saya boleh hubungi mereka?',
        queryEn: 'Who is the Member of Parliament for my constituency and how do I contact them?',
        queryZh: '我的选区议员是谁？我该如何联系他们？',
      },
    ],
  },
];

interface PromptChipsProps {
  onSelect: (query: string) => void;
  disabled?: boolean;
  variant?: 'light' | 'dark';
}

export function PromptChips({ onSelect, disabled, variant = 'light' }: PromptChipsProps) {
  const { t, locale } = useI18n();
  const isDark = variant === 'dark';

  const headerClass = isDark ? 'text-nk-heritage' : 'text-nk-heritage-dim';
  const askChipClass = isDark
    ? 'bg-white/5 hover:bg-nk-official-dim/20 hover:text-nk-official hover:border-nk-official/40 text-zinc-300 border-white/10'
    : 'bg-zinc-100 hover:bg-nk-official/10 hover:text-nk-official-dim hover:border-nk-official/30 text-zinc-600 border-zinc-200';
  // Distinct treatment for chips that hand off to a vertical agent — the
  // brief calls this "must be legible without a legend": a filled tinted
  // pill (vs. the neutral outline of an ask-in-chat chip) plus an arrow
  // glyph is the tell, not a separate label the user has to read first.
  const agentChipClass = isDark
    ? 'bg-nk-official/15 hover:bg-nk-official/25 text-nk-official border-nk-official/30'
    : 'bg-nk-official/10 hover:bg-nk-official/15 text-nk-official-dim border-nk-official/30';

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

  // A chip whose query already matches a vertical agent (per the same rule
  // table ChatInput's live-suggestion banner uses) routes straight to that
  // agent's page instead of firing a generic RAG query — no point asking
  // in chat what a dedicated agent already handles better. Matched on the
  // English query text since agent-suggestions' keyword list is
  // language-mixed (covers BM/EN terms) but always lower-cased substring
  // matching, and the English chip copy reliably contains the trigger word
  // ("EPF", "SSM", "grant", "visa"...).
  const agentFor = (chip: Chip): AgentSuggestion | null =>
    matchAgentRules(chip.queryEn).find((s): s is AgentSuggestion => s.kind === 'agent') ?? null;

  // Each group is a label line followed by ONE horizontally-scrolling row
  // of chips, not a flex-wrap that breaks to a new line mid-group. Wrapping
  // read as cluttered on narrow viewports specifically — a group's chips
  // would break into jagged, unevenly-filled lines (one chip alone on its
  // own row while a sibling group's row was full), which is worse than the
  // horizontal-scroll affordance it's replaced with here (same pattern as
  // ChatGPT/Claude mobile's own suggestion-chip rows: swipe to see more,
  // nothing removed, no jagged wrap). scrollbar-hide keeps the native
  // scrollbar off without hiding the ability to scroll.
  return (
    <div className="flex flex-col gap-3 pb-1">
      {GROUPS.map((group) => (
        <div key={group.titleKey} className="flex flex-col gap-1.5 min-w-0">
          <span className={`flex-shrink-0 text-[11px] font-bold uppercase tracking-wide ${headerClass}`}>
            {t(group.titleKey)}
          </span>
          <div className="flex flex-nowrap items-center gap-2 overflow-x-auto scrollbar-hide -mx-4 px-4 sm:mx-0 sm:px-0">
          {group.chips.map((chip) => {
              const agent = agentFor(chip);
              if (agent) {
                return (
                  <Link
                    key={chip.labelEn}
                    href={agent.href}
                    aria-label={t('chat.chip.opens_agent').replace('{agent}', t(agent.titleKey))}
                    className={`flex-shrink-0 whitespace-nowrap inline-flex items-center gap-1 px-3 py-1.5 border rounded-full text-xs font-medium transition-colors ${agentChipClass}`}
                  >
                    {getLabel(chip)}
                    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3 flex-shrink-0" aria-hidden>
                      <path fillRule="evenodd" d="M12.97 3.97a.75.75 0 0 1 1.06 0l4 4a.75.75 0 0 1 0 1.06l-4 4a.75.75 0 1 1-1.06-1.06l2.72-2.72H3a.75.75 0 0 1 0-1.5h12.69l-2.72-2.72a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                    </svg>
                  </Link>
                );
              }
              return (
                <button
                  key={chip.labelEn}
                  onClick={() => onSelect(getQuery(chip))}
                  disabled={disabled}
                  className={`flex-shrink-0 whitespace-nowrap px-3 py-1.5 border rounded-full text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${askChipClass}`}
                >
                  {getLabel(chip)}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
