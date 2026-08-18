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
