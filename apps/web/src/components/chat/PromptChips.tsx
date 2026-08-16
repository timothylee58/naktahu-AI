'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';
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
  /** Single-stroke inline icon, drawn to match the app's existing
   * heroicon-outline-derived SVGs (ChatInput's mic/send/stop icons) —
   * one per domain group, not per chip, since the group is the visual
   * chunking unit (cognitive-load: ≤4 chips per group, 4 groups total). */
  icon: ReactNode;
  chips: Chip[];
}

// Same 10 example queries as before, regrouped into 4 domain clusters
// instead of one flat 10-item row (Chunking rule: ≤4 per group). Grouping
// mirrors the domains these queries actually route to via matchAgentRules
// below, not an arbitrary taxonomy.
const GROUPS: ChipGroup[] = [
  {
    titleKey: 'chat.groups.tax_epf',
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden>
        <path d="M10.75 10.818v2.614A3.13 3.13 0 0 0 11.888 13c.482-.315.612-.648.612-.875 0-.227-.13-.56-.612-.875a3.13 3.13 0 0 0-1.138-.432ZM8.33 8.62c.16.081.331.15.512.204V6.21a3.13 3.13 0 0 0-1.138.432c-.482.315-.612.648-.612.875 0 .227.13.56.612.875.21.137.446.245.626.328Z" />
        <path fillRule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0ZM9.25 4.75a.75.75 0 0 1 1.5 0v.316a4.623 4.623 0 0 1 1.913.752c.5.325 1.087.918 1.087 1.782a.75.75 0 0 1-1.5 0c0-.227-.13-.56-.612-.875a3.13 3.13 0 0 0-.888-.376v2.847c.855.147 1.65.462 2.238.921.629.49 1.012 1.163 1.012 1.933 0 .77-.383 1.443-1.012 1.933-.588.459-1.383.774-2.238.92v.32a.75.75 0 0 1-1.5 0v-.32a4.62 4.62 0 0 1-1.912-.753c-.5-.324-1.088-.918-1.088-1.782a.75.75 0 0 1 1.5 0c0 .227.13.56.612.876.238.155.5.264.888.376V9.15c-.855-.147-1.65-.462-2.238-.921C6.383 7.739 6 7.066 6 6.296c0-.77.383-1.442 1.012-1.933.588-.459 1.383-.774 2.238-.92v-.693Z" clipRule="evenodd" />
      </svg>
    ),
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
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden>
        <path d="M6 3.75A2.75 2.75 0 0 1 8.75 1h2.5A2.75 2.75 0 0 1 14 3.75v.443c.572.055 1.14.122 1.706.2C17.053 4.582 18 5.75 18 7.07v3.469c0 1.126-.694 2.191-1.83 2.54-1.952.599-4.024.921-6.17.921s-4.219-.322-6.17-.921C2.694 12.73 2 11.665 2 10.539V7.07c0-1.321.947-2.489 2.294-2.676A41.047 41.047 0 0 1 6 4.193V3.75Zm6.5 0v.325a41.622 41.622 0 0 0-5 0V3.75c0-.69.56-1.25 1.25-1.25h2.5c.69 0 1.25.56 1.25 1.25ZM10 10a1 1 0 0 0-1 1v.01a1 1 0 0 0 1 1h.01a1 1 0 0 0 1-1V11a1 1 0 0 0-1-1H10Z" />
        <path d="M3 15.055v-.684c.126.053.255.1.39.142 2.092.642 4.313.987 6.61.987 2.297 0 4.518-.345 6.61-.987.135-.041.264-.089.39-.142v.684c0 1.347-.985 2.53-2.363 2.686a41.454 41.454 0 0 1-9.274 0C3.985 17.585 3 16.402 3 15.055Z" />
      </svg>
    ),
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
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden>
        <path fillRule="evenodd" d="M4 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4Zm10 0H6v12h8V4Z" clipRule="evenodd" />
        <path d="M10 5.5a1.75 1.75 0 1 0 0 3.5 1.75 1.75 0 0 0 0-3.5ZM7.5 12.25c0-1.036 1.12-1.75 2.5-1.75s2.5.714 2.5 1.75a.5.5 0 0 1-.5.5h-4a.5.5 0 0 1-.5-.5Z" />
      </svg>
    ),
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
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4" aria-hidden>
        <path d="M10.394 2.08a1 1 0 0 0-.788 0l-7 3a1 1 0 0 0 0 1.84L5.25 8.051a.999.999 0 0 1 .356-.257l4-1.714a.75.75 0 0 1 .592 1.38L7.667 8.667l1.94.831a1 1 0 0 0 .787 0l7-3a1 1 0 0 0 0-1.838l-7-3ZM3.31 9.397 5 10.12v4.102a8.969 8.969 0 0 0-1.05-.174 1 1 0 0 1-.89-.89 11.115 11.115 0 0 1 .25-3.762ZM9.3 16.5l-2.995-1.285a5.985 5.985 0 0 1-.014-3.335l1.914.822a2.5 2.5 0 0 0 1.965 0l1.914-.822a5.984 5.984 0 0 1-.014 3.335L9.3 16.5Z" />
      </svg>
    ),
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

  return (
    <div className="flex flex-col gap-2.5 pb-1">
      {GROUPS.map((group) => (
        <div key={group.titleKey} className="flex flex-col gap-1.5">
          <div className={`flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide ${headerClass}`}>
            {group.icon}
            <span>{t(group.titleKey)}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {group.chips.map((chip) => {
              const agent = agentFor(chip);
              if (agent) {
                return (
                  <Link
                    key={chip.labelEn}
                    href={agent.href}
                    aria-label={t('chat.chip.opens_agent').replace('{agent}', t(agent.titleKey))}
                    className={`inline-flex items-center gap-1 px-3 py-1.5 border rounded-full text-xs font-medium transition-colors ${agentChipClass}`}
                  >
                    {getLabel(chip)}
                    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3" aria-hidden>
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
                  className={`px-3 py-1.5 border rounded-full text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${askChipClass}`}
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
