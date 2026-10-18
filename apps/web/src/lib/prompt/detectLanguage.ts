export type DetectedLanguage = 'ms' | 'en' | 'zh';

// Client-side guess shown in the box badge while typing. The real language
// decision is still made by the backend router_node after submit; this only
// has to be right often enough to set expectations, so it stays a cheap
// stopword vote rather than a model.
const MS_WORDS = new Set([
  'yang', 'dan', 'untuk', 'apa', 'apakah', 'bagaimana', 'macam', 'nak', 'saya', 'boleh', 'di', 'ke',
  'dengan', 'ini', 'itu', 'tak', 'tidak', 'adakah', 'cara', 'berapa', 'bila', 'kalau', 'mana', 'kos',
  'daftar', 'ganti', 'hilang', 'cukai', 'dari', 'atau', 'pada', 'akan', 'sudah', 'perlu', 'patut',
  'buat', 'semak', 'mohon', 'permohonan', 'tarikh', 'akhir', 'kerajaan',
]);
const EN_WORDS = new Set([
  'the', 'how', 'what', 'do', 'does', 'my', 'to', 'is', 'are', 'can', 'i', 'for', 'of', 'and', 'a',
  'in', 'when', 'where', 'which', 'should', 'much', 'if', 'lose', 'lost', 'renew', 'apply', 'need',
  'check', 'register', 'pay', 'get', 'with', 'about', 'deadline', 'filing',
]);
const CJK = /[㐀-鿿]/g;

export function detectLanguage(text: string): DetectedLanguage | null {
  const trimmed = text.trim();
  if (trimmed.length < 3) return null;

  const cjk = (trimmed.match(CJK) ?? []).length;
  if (cjk >= 2 && cjk / trimmed.length > 0.2) return 'zh';

  let ms = 0;
  let en = 0;
  for (const word of trimmed.toLowerCase().split(/[^\p{L}]+/u)) {
    if (!word) continue;
    if (MS_WORDS.has(word)) ms++;
    if (EN_WORDS.has(word)) en++;
  }
  if (ms === en) return null;
  return ms > en ? 'ms' : 'en';
}
