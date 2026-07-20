import { calculateLocalAllocatedUsd } from './api';

describe('calculateLocalAllocatedUsd', () => {
  it('preserves calculated allocations below $25', () => {
    expect(calculateLocalAllocatedUsd(100, 100, 1)).toBe(1);
    expect(calculateLocalAllocatedUsd(500, 500, 2)).toBe(10);
  });

  it('uses the configured value as the exact hard maximum in dollar mode', () => {
    expect(calculateLocalAllocatedUsd(1000, 1000, 10, 'dollar')).toBe(10);
    expect(calculateLocalAllocatedUsd(5, 5, 10, 'dollar')).toBe(10);
  });

  it('preserves a disabled zero allocation', () => {
    expect(calculateLocalAllocatedUsd(100, 100, 0)).toBe(0);
  });

  it('does not create a negative allocation', () => {
    expect(calculateLocalAllocatedUsd(100, 100, -1)).toBe(0);
  });

  it('rejects non-finite capital and sizing inputs', () => {
    expect(calculateLocalAllocatedUsd(Number.POSITIVE_INFINITY, 100, 1)).toBe(1);
    expect(calculateLocalAllocatedUsd(Number.NaN, Number.NaN, 1)).toBe(0);
    expect(calculateLocalAllocatedUsd(100, 100, Number.NaN)).toBe(0);
  });
});