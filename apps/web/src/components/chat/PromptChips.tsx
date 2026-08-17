'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, MotionConfig, useScroll, useTransform } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { matchAgentRules, type AgentSuggestion } from '@/lib/agent-suggestions';

// framer-motion v12's replacement for the deprecated motion(Component)
// factory — lets a Next.js <Link> take whileTap/variants like any other
// motion element.
const MotionLink = motion.create(Link);

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

// Same 10 example queries as before, in the same 4 domain clusters.
// Grouping mirrors the domains these queries actually route to via
// matchAgentRules below, not an arbitrary taxonomy.
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

/**
 * Suggestion chips as a segmented category selector.
 *
 * Previously all 4 groups rendered stacked at once (4 label rows + 4 chip
 * rows = 8 rows of vertical space), which read as cluttered and as four
 * bold labels competing for the same attention. Now the group labels ARE
 * the control: a tab strip whose active pill slides between categories via
 * a shared layoutId, with only the active category's chips rendered below.
 * Two rows total instead of eight.
 *
 * Uses the WAI-ARIA tabs pattern with automatic activation (arrow keys move
 * and select in one step) — the standard for a tablist whose panels are
 * cheap to swap, which these are.
 */
export function PromptChips({ onSelect, disabled, variant = 'light' }: PromptChipsProps) {
  const { t, locale } = useI18n();
  const isDark = variant === 'dark';
  const [active, setActive] = useState(0);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const activeTabClass = isDark ? 'text-nk-heritage' : 'text-nk-heritage-dim';
  const idleTabClass = isDark
    ? 'text-zinc-500 hover:text-zinc-300'
    : 'text-zinc-400 hover:text-zinc-600';
  const pillClass = isDark ? 'bg-nk-heritage/15' : 'bg-nk-heritage/10';
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

  const selectTab = useCallback((index: number) => {
    const next = (index + GROUPS.length) % GROUPS.length;
    setActive(next);
    tabRefs.current[next]?.focus();
    // Keep the newly-active tab visible when the strip itself is scrolled
    // (4 category names overflow a narrow viewport), so arrow-keying to an
    // off-screen tab doesn't move focus somewhere the user can't see.
    tabRefs.current[next]?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, []);

  const onTabKeyDown = useCallback(
    (e: React.KeyboardEvent, index: number) => {
      if (e.key === 'ArrowRight') { e.preventDefault(); selectTab(index + 1); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); selectTab(index - 1); }
      else if (e.key === 'Home') { e.preventDefault(); selectTab(0); }
      else if (e.key === 'End') { e.preventDefault(); selectTab(GROUPS.length - 1); }
    },
    [selectTab],
  );

  const activeGroup = GROUPS[active];

  return (
    // reducedMotion="user" is how motion reduction is honoured here, rather
    // than branching variants/initial on useReducedMotion(). That branching
    // is an SSR hydration bug: useReducedMotion() is false on the server and
    // true on a reduced-motion client, so the two render DIFFERENT inline
    // styles (server style={{opacity:"1"}} vs client style={{}}) and React
    // logs a mismatch it says it "won't patch up". Passing identical props
    // in both environments and letting MotionConfig strip the animations at
    // runtime keeps the markup byte-identical. It also gives more correct
    // semantics than the manual branch did: framer-motion drops transforms
    // (the y-offsets, the scale-on-tap, the layout spring) while keeping
    // opacity fades, which is what reduced-motion is actually asking for —
    // movement is the problem, not cross-fades.
    <MotionConfig reducedMotion="user">
    <div className="flex flex-col gap-2">
      {/* Tab strip. Horizontally scrollable because 4 category names (esp.
          in BM: "Imigresen & Dokumen") overflow a phone viewport. */}
      <div
        role="tablist"
        aria-label={t('chat.groups.tablist_label')}
        aria-orientation="horizontal"
        className="flex flex-nowrap items-center gap-1 overflow-x-auto scrollbar-hide -mx-4 px-4 sm:mx-0 sm:px-0"
      >
        {GROUPS.map((group, i) => {
          const selected = i === active;
          return (
            <button
              key={group.titleKey}
              ref={(el) => { tabRefs.current[i] = el; }}
              role="tab"
              id={`prompt-tab-${i}`}
              aria-selected={selected}
              aria-controls={`prompt-panel-${i}`}
              // Roving tabindex: only the active tab is in the page's tab
              // order; arrow keys move between tabs from there (WAI-ARIA
              // tabs pattern), so Tab doesn't have to walk all 4.
              tabIndex={selected ? 0 : -1}
              onClick={() => selectTab(i)}
              onKeyDown={(e) => onTabKeyDown(e, i)}
              className={`relative flex-shrink-0 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide transition-colors ${
                selected ? activeTabClass : idleTabClass
              }`}
            >
              {selected && (
                <motion.span
                  // The signature shared-layout move: one element whose
                  // layoutId is stable across tabs, so framer-motion slides
                  // it from the old tab to the new one instead of
                  // cross-fading two separate backgrounds.
                  layoutId="prompt-chip-tab-pill"
                  className={`absolute inset-0 rounded-full ${pillClass}`}
                  transition={{ type: 'spring', stiffness: 420, damping: 34, mass: 0.7 }}
                />
              )}
              <span className="relative z-10">{t(group.titleKey)}</span>
            </button>
          );
        })}
      </div>

      {/* Panel. min-h reserves the row's height so the empty beat between
          exit and enter (AnimatePresence mode="wait") doesn't collapse the
          container and shift everything below it. */}
      <div
        role="tabpanel"
        id={`prompt-panel-${active}`}
        aria-labelledby={`prompt-tab-${active}`}
        className="min-h-[30px]"
      >
        <AnimatePresence mode="wait" initial={false}>
          <ChipRow
            key={activeGroup.titleKey}
            group={activeGroup}
            isDark={isDark}
            disabled={disabled}
            askChipClass={askChipClass}
            agentChipClass={agentChipClass}
            getLabel={getLabel}
            getQuery={getQuery}
            agentFor={agentFor}
            onSelect={onSelect}
            opensAgentLabel={(agent: AgentSuggestion) =>
              t('chat.chip.opens_agent').replace('{agent}', t(agent.titleKey))
            }
          />
        </AnimatePresence>
      </div>
    </div>
    </MotionConfig>
  );
}

interface ChipRowProps {
  group: ChipGroup;
  isDark: boolean;
  disabled?: boolean;
  askChipClass: string;
  agentChipClass: string;
  getLabel: (chip: Chip) => string;
  getQuery: (chip: Chip) => string;
  agentFor: (chip: Chip) => AgentSuggestion | null;
  onSelect: (query: string) => void;
  opensAgentLabel: (agent: AgentSuggestion) => string;
}

const rowVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.035 } },
  exit: { opacity: 0, transition: { duration: 0.1 } },
};
const chipVariants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: 'easeOut' as const } },
  exit: { opacity: 0 },
};

/** The active category's chips, plus a scroll-position indicator for when
 * that row overflows. Split out so useScroll gets a fresh hook instance per
 * mounted row — AnimatePresence remounts this on every tab change. */
function ChipRow({
  group,
  isDark,
  disabled,
  askChipClass,
  agentChipClass,
  getLabel,
  getQuery,
  agentFor,
  onSelect,
  opensAgentLabel,
}: ChipRowProps) {
  const rowRef = useRef<HTMLDivElement>(null);
  const [overflowing, setOverflowing] = useState(false);
  const { scrollXProgress } = useScroll({ container: rowRef });
  // A fixed-width thumb sliding across the track, not a literally
  // proportional scrollbar (which would shrink to near-nothing for a
  // 2-4-chip row and stop being visible as a UI element at all) — just
  // enough to signal "there's more, swipe" and roughly where you are.
  const thumbLeft = useTransform(scrollXProgress, [0, 1], ['0%', '75%']);

  // Only show the indicator when the row actually overflows — a 2-chip
  // group that fits its full width shouldn't get a "swipe for more"
  // affordance for content that isn't actually swipeable.
  useEffect(() => {
    const el = rowRef.current;
    if (!el) return;
    const check = () => setOverflowing(el.scrollWidth > el.clientWidth + 1);
    check();
    const observer = new ResizeObserver(check);
    observer.observe(el);
    window.addEventListener('resize', check);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', check);
    };
  }, [group]);

  const trackClass = isDark ? 'bg-white/10' : 'bg-zinc-200';
  const thumbClass = isDark ? 'bg-nk-official/60' : 'bg-nk-official/50';

  return (
    <motion.div variants={rowVariants} initial="hidden" animate="show" exit="exit">
      <div
        ref={rowRef}
        className="flex flex-nowrap items-center gap-2 overflow-x-auto scrollbar-hide -mx-4 px-4 sm:mx-0 sm:px-0"
      >
        {group.chips.map((chip) => {
          const agent = agentFor(chip);
          if (agent) {
            return (
              <MotionLink
                key={chip.labelEn}
                href={agent.href}
                aria-label={opensAgentLabel(agent)}
                variants={chipVariants}
                whileTap={{ scale: 0.96 }}
                className={`flex-shrink-0 whitespace-nowrap inline-flex items-center gap-1 px-3 py-1.5 border rounded-full text-xs font-medium transition-colors ${agentChipClass}`}
              >
                {getLabel(chip)}
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3 flex-shrink-0" aria-hidden>
                  <path fillRule="evenodd" d="M12.97 3.97a.75.75 0 0 1 1.06 0l4 4a.75.75 0 0 1 0 1.06l-4 4a.75.75 0 1 1-1.06-1.06l2.72-2.72H3a.75.75 0 0 1 0-1.5h12.69l-2.72-2.72a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                </svg>
              </MotionLink>
            );
          }
          return (
            <motion.button
              key={chip.labelEn}
              onClick={() => onSelect(getQuery(chip))}
              disabled={disabled}
              variants={chipVariants}
              whileTap={disabled ? undefined : { scale: 0.96 }}
              className={`flex-shrink-0 whitespace-nowrap px-3 py-1.5 border rounded-full text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${askChipClass}`}
            >
              {getLabel(chip)}
            </motion.button>
          );
        })}
      </div>
      {overflowing && (
        <div className={`relative h-1 rounded-full overflow-hidden mt-1.5 ${trackClass}`} aria-hidden>
          <motion.div className={`absolute inset-y-0 w-1/4 rounded-full ${thumbClass}`} style={{ left: thumbLeft }} />
        </div>
      )}
    </motion.div>
  );
}
