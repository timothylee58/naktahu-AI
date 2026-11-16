import { describe, expect, it } from 'vitest';

import { LOW_CONFIDENCE_THRESHOLD, shouldWarnLowConfidence } from './answer-warning';

describe('shouldWarnLowConfidence', () => {
  it('warns on a low confidence number, as before', () => {
    expect(shouldWarnLowConfidence(0.35, false)).toBe(true);
    expect(shouldWarnLowConfidence(LOW_CONFIDENCE_THRESHOLD - 0.01, undefined)).toBe(true);
  });

  it('does not warn at or above the threshold when nothing was flagged', () => {
    expect(shouldWarnLowConfidence(LOW_CONFIDENCE_THRESHOLD, false)).toBe(false); // the cut-off is exclusive
    expect(shouldWarnLowConfidence(0.83, false)).toBe(false);
    expect(shouldWarnLowConfidence(0.83, undefined)).toBe(false);
  });

  it('warns when the backend flagged the answer, even at a high confidence', () => {
    expect(shouldWarnLowConfidence(0.83, true)).toBe(true);
    expect(shouldWarnLowConfidence(0.68, true)).toBe(true);
  });

  it('stays quiet while there is no confidence yet and nothing flagged', () => {
    expect(shouldWarnLowConfidence(null, false)).toBe(false);
    expect(shouldWarnLowConfidence(undefined, undefined)).toBe(false);
  });
});
