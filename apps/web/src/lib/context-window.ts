/** Marketing / plan context window size (characters). */
export const CONTEXT_WINDOW_CHARS = 200_000;

export function formatContextUsage(usedChars: number): string {
  if (usedChars >= 1_000) {
    return `${(usedChars / 1_000).toFixed(usedChars >= 10_000 ? 0 : 1)}K`;
  }
  return String(usedChars);
}

export function contextUsagePercent(usedChars: number): number {
  return Math.min(100, (usedChars / CONTEXT_WINDOW_CHARS) * 100);
}
