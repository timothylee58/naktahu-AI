import { describe, expect, it } from 'vitest';
import { allOfficial, latestChecked, sourceRows } from './citations';
import type { Citation } from './types';

const c = (over: Partial<Citation>): Citation => ({ ministry: 'LHDN', url: 'https://www.hasil.gov.my/a', ...over });

describe('sourceRows', () => {
  it('dedupes by URL, strips www., and keeps the tier only when it is a known value', () => {
    const rows = sourceRows([
      c({ source_tier: 'official' }),
      c({ ministry: 'dup', source_tier: 'community' }),
      c({ url: 'https://mymp.org.my/', ministry: 'MyMP', source_tier: 'community' }),
      c({ url: 'https://www.ssm.com.my/x', ministry: 'SSM', source_tier: null }),
    ]);
    expect(rows.map((r) => r.host)).toEqual(['hasil.gov.my', 'mymp.org.my', 'ssm.com.my']);
    expect(rows.map((r) => r.tier)).toEqual(['official', 'community', null]);
  });

  it('drops citations without a real http(s) URL instead of inventing a link', () => {
    expect(sourceRows([c({ url: undefined }), c({ url: 'javascript:alert(1)' }), c({ url: 'not a url' }), c({ url: '' })])).toEqual([]);
  });

  it('falls back to source_url', () => {
    expect(sourceRows([{ ministry: 'X', source_url: 'https://moh.gov.my/p' }])[0].host).toBe('moh.gov.my');
  });
});

describe('allOfficial', () => {
  it('is true only when every row is official', () => {
    const row = (tier: 'official' | 'community' | null) => ({ url: 'u', host: 'h', ministry: 'm', tier });
    expect(allOfficial([row('official'), row('official')])).toBe(true);
    expect(allOfficial([row('official'), row(null)])).toBe(false);
    expect(allOfficial([row('official'), row('community')])).toBe(false);
    expect(allOfficial([])).toBe(false);
  });
});

describe('latestChecked', () => {
  it('picks the newest valid timestamp and ignores bad or missing ones', () => {
    const d = latestChecked([
      c({ retrieved_at: '2026-08-01T00:00:00Z' }),
      c({ retrieved_at: '2026-09-30T12:00:00Z' }),
      c({ retrieved_at: 'garbage' }),
      c({ retrieved_at: null }),
      c({}),
    ]);
    expect(d?.toISOString()).toBe('2026-09-30T12:00:00.000Z');
  });

  it('returns null when nothing has a date: no fabricated "today"', () => {
    expect(latestChecked([c({}), c({ retrieved_at: 'nope' })])).toBeNull();
  });
});
