import { describe, expect, it } from 'vitest';
import {
  asCrowd,
  directionsUrl,
  EMPTY_CROWD,
  fill,
  freshnessTone,
  haversineM,
  segmentCount,
  stepIndex,
} from './crowd';

describe('asCrowd', () => {
  it('returns the empty crowd for null', () => {
    expect(asCrowd(null)).toBe(EMPTY_CROWD);
  });

  it('keeps known fields and drops malformed ones', () => {
    const crowd = asCrowd({
      status: 'packed',
      is_fresh: true,
      report_count: 7,
      last_updated: '2026-10-21T04:00:00Z',
      counts: { empty: 1, moderate: 'x', packed: 6 },
      hour_status: 'nope',
    });
    expect(crowd.status).toBe('packed');
    expect(crowd.counts).toEqual({ empty: 1, moderate: 0, packed: 6 });
    expect(crowd.hour_status).toBeNull();
  });

  it('treats a non-true is_fresh as stale', () => {
    expect(asCrowd({ status: 'empty', is_fresh: 'yes' }).is_fresh).toBe(false);
  });
});

describe('segmentCount', () => {
  it('maps each level to 1, 2 and 3 segments', () => {
    expect([segmentCount('empty'), segmentCount('moderate'), segmentCount('packed')]).toEqual([1, 2, 3]);
  });
});

describe('stepIndex', () => {
  it('starts at the ends when nothing is active', () => {
    expect(stepIndex(-1, 1, 4)).toBe(0);
    expect(stepIndex(-1, -1, 4)).toBe(3);
  });

  it('wraps in both directions', () => {
    expect(stepIndex(3, 1, 4)).toBe(0);
    expect(stepIndex(0, -1, 4)).toBe(3);
  });

  it('is -1 for an empty list', () => {
    expect(stepIndex(0, 1, 0)).toBe(-1);
  });
});

describe('freshnessTone', () => {
  it('separates no reports, fresh and stale', () => {
    expect(freshnessTone(EMPTY_CROWD)).toBe('none');
    expect(freshnessTone({ ...EMPTY_CROWD, status: 'empty', is_fresh: true })).toBe('fresh');
    expect(freshnessTone({ ...EMPTY_CROWD, status: 'empty', is_fresh: false })).toBe('stale');
  });
});

describe('directionsUrl', () => {
  it('prefers coordinates, falls back to an encoded name', () => {
    expect(directionsUrl({ name: 'A', lat: 3.1, lng: 101.7 })).toContain('query=3.1,101.7');
    expect(directionsUrl({ name: 'Pak Mat & Co', lat: null, lng: null })).toContain('Pak%20Mat%20%26%20Co');
  });
});

describe('haversineM', () => {
  it('is zero for the same point and roughly 111 km per degree of latitude', () => {
    expect(haversineM({ lat: 3, lng: 101 }, { lat: 3, lng: 101 })).toBe(0);
    const km = haversineM({ lat: 3, lng: 101 }, { lat: 4, lng: 101 }) / 1000;
    expect(km).toBeGreaterThan(110);
    expect(km).toBeLessThan(112);
  });
});

describe('fill', () => {
  it('replaces every placeholder', () => {
    expect(fill('{a} and {a} and {b}', { a: 1, b: 'x' })).toBe('1 and 1 and x');
  });
});
