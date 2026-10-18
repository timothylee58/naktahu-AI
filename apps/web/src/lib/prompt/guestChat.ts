// The query endpoint answers 429 with a message starting "Daily query limit
// reached" when the free daily quota is spent (app/routers/query.py); the
// other 429 (hourly rate limit) must NOT be shown as "free questions used up".
export function isDailyLimitError(error: string | null | undefined): boolean {
  return !!error && error.startsWith('HTTP 429') && error.includes('Daily query limit');
}

// How much of the layout viewport the on-screen keyboard covers. iOS Safari
// keeps the layout viewport full-height while the keyboard is open, so a
// bottom-docked input sits underneath it unless we lift it by this amount.
export function keyboardInset(innerHeight: number, viewportHeight: number, viewportOffsetTop: number): number {
  const covered = innerHeight - viewportHeight - viewportOffsetTop;
  // Sub-100px changes are browser chrome (URL bar) collapsing, not a keyboard.
  return covered > 100 ? Math.round(covered) : 0;
}
