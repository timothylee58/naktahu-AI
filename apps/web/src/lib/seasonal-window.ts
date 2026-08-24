// Merdeka (31 Aug) + Hari Malaysia (16 Sep) — one shared window covering
// both, live for a few days either side rather than exactly on the two
// dates. Checked by month/day only (year-agnostic) so nothing here needs
// touching next year. Extracted from SeasonalBanner.tsx so a second seasonal
// surface (the landing-page hero video) doesn't duplicate this a third time.
export const SEASONAL_WINDOW_START = { month: 8, day: 25 } as const; // 25 Aug
export const SEASONAL_WINDOW_END = { month: 9, day: 20 } as const; // 20 Sep

export function inSeasonalWindow(now: Date): boolean {
  const month = now.getMonth() + 1;
  const day = now.getDate();
  const value = month * 100 + day;
  return (
    value >= SEASONAL_WINDOW_START.month * 100 + SEASONAL_WINDOW_START.day &&
    value <= SEASONAL_WINDOW_END.month * 100 + SEASONAL_WINDOW_END.day
  );
}

// The two actual dates the window (Aug 25 - Sep 20) surrounds — used by
// the hero video's countdown caption to say something more specific than
// "it's the season" (e.g. "3 days to Merdeka Day" vs. "Happy Malaysia
// Day!"). Only meaningful when inSeasonalWindow(now) is already true;
// callers gate on that separately (same split as every other consumer of
// this module).
const MERDEKA_MONTH = 8;
const MERDEKA_DAY = 31;
const MALAYSIA_DAY_MONTH = 9;
const MALAYSIA_DAY_DAY = 16;

export type SeasonalMilestone =
  | { kind: 'before_merdeka'; days: number }
  | { kind: 'merdeka_day' }
  | { kind: 'before_malaysia_day'; days: number }
  | { kind: 'malaysia_day' }
  | { kind: 'after' };

function daysUntil(now: Date, month: number, day: number): number {
  const target = new Date(now.getFullYear(), month - 1, day);
  const startOfNow = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((target.getTime() - startOfNow.getTime()) / 86_400_000);
}

// Shared keyword detector — a small, deliberately narrow set (not a
// general "excited" detector) so any Merdeka-themed UI reaction (chat's
// confetti, the send-button flag pulse, the post-answer state-narrowing
// chip) reads as a direct response to the user's own words, not a random
// surprise. Extracted from app/chat/page.tsx so its two new consumers
// (ChatInput's send-button pulse, ChatBubble's state-narrowing chip)
// don't each duplicate the list.
const KEMERDEKAAN_KEYWORDS = ['merdeka', 'perarakan', 'hari malaysia', 'negaraku'];

export function mentionsKemerdekaan(query: string): boolean {
  const lower = query.toLowerCase();
  return KEMERDEKAAN_KEYWORDS.some((kw) => lower.includes(kw));
}

export function getSeasonalMilestone(now: Date): SeasonalMilestone {
  const month = now.getMonth() + 1;
  const day = now.getDate();
  const value = month * 100 + day;
  const merdekaValue = MERDEKA_MONTH * 100 + MERDEKA_DAY;
  const malaysiaDayValue = MALAYSIA_DAY_MONTH * 100 + MALAYSIA_DAY_DAY;

  if (value < merdekaValue) return { kind: 'before_merdeka', days: daysUntil(now, MERDEKA_MONTH, MERDEKA_DAY) };
  if (value === merdekaValue) return { kind: 'merdeka_day' };
  if (value < malaysiaDayValue) {
    return { kind: 'before_malaysia_day', days: daysUntil(now, MALAYSIA_DAY_MONTH, MALAYSIA_DAY_DAY) };
  }
  if (value === malaysiaDayValue) return { kind: 'malaysia_day' };
  return { kind: 'after' };
}
