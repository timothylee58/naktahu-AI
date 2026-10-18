import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { detectLanguage } from './detectLanguage';
import { HANDOFF_TTL_MS, savePending, takePending } from './handoff';
import { hasMyKad, stripMyKad } from './piiGuard';
import { isDailyLimitError, keyboardInset } from './guestChat';
import { decideSubmit, initialPromptState, isComposingEnter, promptReducer } from './promptState';

class MemoryStorage {
  private data = new Map<string, string>();
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.data.set(k, v);
  }
  removeItem(k: string) {
    this.data.delete(k);
  }
}

describe('piiGuard', () => {
  it.each(['900101-14-5678', '900101145678', 'my ic is 900101-14-5678 ok'])('detects %s', (s) => {
    expect(hasMyKad(s)).toBe(true);
  });

  it.each(['', 'renew passport', '12345', '9001011456789012', 'call 03-1234 5678'])('ignores %s', (s) => {
    expect(hasMyKad(s)).toBe(false);
  });

  it('is stable across repeated calls (no sticky regex state)', () => {
    expect([hasMyKad('900101-14-5678'), hasMyKad('900101-14-5678')]).toEqual([true, true]);
  });

  it('strips the number and collapses whitespace', () => {
    expect(stripMyKad('IC 900101-14-5678 hilang')).toBe('IC hilang');
  });
});

describe('detectLanguage', () => {
  it('detects English', () => expect(detectLanguage('How do I renew my passport?')).toBe('en'));
  it('detects Malay', () => expect(detectLanguage('Apa patut saya buat kalau MyKad hilang?')).toBe('ms'));
  it('detects Chinese', () => expect(detectLanguage('如何申请护照')).toBe('zh'));
  it('returns null when too short or ambiguous', () => {
    expect(detectLanguage('hi')).toBeNull();
    expect(detectLanguage('MyKad')).toBeNull();
  });
});

describe('handoff', () => {
  beforeEach(() => {
    (globalThis as unknown as { sessionStorage: MemoryStorage }).sessionStorage = new MemoryStorage();
  });
  afterEach(() => {
    delete (globalThis as { sessionStorage?: unknown }).sessionStorage;
  });

  it('round-trips once and removes the entry', () => {
    expect(savePending({ q: ' hello ', source: 'typed', uiLocale: 'en' })).toBe(true);
    expect(takePending()?.q).toBe('hello');
    expect(takePending()).toBeNull();
  });

  it('expires after the TTL', () => {
    savePending({ q: 'old', source: 'typed', uiLocale: 'ms' });
    expect(takePending(Date.now() + HANDOFF_TTL_MS + 1)).toBeNull();
  });

  it('rejects malformed JSON and empty questions', () => {
    sessionStorage.setItem('nk:pending', '{nope');
    expect(takePending()).toBeNull();
    savePending({ q: '   ', source: 'typed', uiLocale: 'ms' });
    expect(takePending()).toBeNull();
  });

  it('survives unavailable storage', () => {
    delete (globalThis as { sessionStorage?: unknown }).sessionStorage;
    expect(savePending({ q: 'x', source: 'typed', uiLocale: 'ms' })).toBe(false);
    expect(takePending()).toBeNull();
  });
});

describe('promptState', () => {
  it('ignores an empty or whitespace submit', () => {
    expect(decideSubmit(initialPromptState)).toEqual({ kind: 'ignore' });
    expect(decideSubmit(promptReducer(initialPromptState, { type: 'type', value: '   ' }))).toEqual({ kind: 'ignore' });
  });

  it('sends trimmed text', () => {
    const s = promptReducer(initialPromptState, { type: 'type', value: '  renew passport ' });
    expect(decideSubmit(s)).toEqual({ kind: 'send', text: 'renew passport' });
  });

  it('warns on the first submit with a MyKad number and sends on the second', () => {
    let s = promptReducer(initialPromptState, { type: 'type', value: 'ic 900101-14-5678' });
    expect(decideSubmit(s)).toEqual({ kind: 'warn' });
    s = promptReducer(s, { type: 'acknowledgePii' });
    expect(decideSubmit(s).kind).toBe('send');
  });

  it('editing after acknowledging re-arms the warning', () => {
    let s = promptReducer(initialPromptState, { type: 'type', value: 'ic 900101-14-5678' });
    s = promptReducer(s, { type: 'acknowledgePii' });
    s = promptReducer(s, { type: 'type', value: 'ic 900101-14-5678 please' });
    expect(decideSubmit(s)).toEqual({ kind: 'warn' });
  });

  it('stripPii removes the number so the text sends without a warning', () => {
    let s = promptReducer(initialPromptState, { type: 'type', value: 'ic 900101-14-5678 hilang' });
    s = promptReducer(s, { type: 'stripPii' });
    expect(s.value).toBe('ic hilang');
    expect(decideSubmit(s).kind).toBe('send');
  });

  it('fill replaces the draft and clear empties it', () => {
    let s = promptReducer(initialPromptState, { type: 'fill', value: 'Cara bayar cukai' });
    expect(s.value).toBe('Cara bayar cukai');
    s = promptReducer(s, { type: 'clear' });
    expect(s).toEqual(initialPromptState);
  });

  it('caps input length', () => {
    expect(promptReducer(initialPromptState, { type: 'type', value: 'a'.repeat(5000) }).value).toHaveLength(1000);
  });

  it('treats Enter during IME composition as not-a-submit', () => {
    expect(isComposingEnter({ nativeEvent: { isComposing: true } })).toBe(true);
    expect(isComposingEnter({ keyCode: 229 })).toBe(true);
    expect(isComposingEnter({ nativeEvent: { isComposing: false }, keyCode: 13 })).toBe(false);
  });
});

describe('guestChat', () => {
  it('recognises only the daily-limit 429', () => {
    expect(isDailyLimitError('HTTP 429: {"detail":"Daily query limit reached (25/day on the free plan)."}')).toBe(true);
    expect(isDailyLimitError('HTTP 429: {"error":"Rate limit exceeded: 30 per 1 hour"}')).toBe(false);
    expect(isDailyLimitError('HTTP 500: Daily query limit')).toBe(false);
    expect(isDailyLimitError(null)).toBe(false);
  });

  it('reports the keyboard height and ignores URL-bar jitter', () => {
    expect(keyboardInset(800, 480, 0)).toBe(320);
    expect(keyboardInset(800, 740, 0)).toBe(0);
    expect(keyboardInset(800, 800, 0)).toBe(0);
    // iOS scrolls the visual viewport when the keyboard opens.
    expect(keyboardInset(800, 480, 40)).toBe(280);
  });
});
