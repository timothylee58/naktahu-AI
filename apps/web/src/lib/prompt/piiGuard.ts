// 6-2-4 digits with optional hyphens covers both "900101-14-5678" and the
// bare 12-digit form people paste.
const MYKAD = /\b\d{6}-?\d{2}-?\d{4}\b/g;

export function hasMyKad(text: string): boolean {
  MYKAD.lastIndex = 0;
  return MYKAD.test(text);
}

export function stripMyKad(text: string): string {
  return text.replace(MYKAD, '').replace(/\s{2,}/g, ' ').trim();
}
