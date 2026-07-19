import { calculateLocalAllocatedUsd } from './api';

describe('calculateLocalAllocatedUsd', () => {
  it('preserves calculated allocations below $25', () => {
    expect(calculateLocalAllocatedUsd(100, 100, 1)).toBe(1);
    expect(calculateLocalAllocatedUsd(500, 500, 2)).toBe(10);
  });

  it('preserves a disabled zero allocation', () => {
    expect(calculateLocalAllocatedUsd(100, 100, 0)).toBe(0);
  });

  it('does not create a negative allocation', () => {
    expect(calculateLocalAllocatedUsd(100, 100, -1)).toBe(0);
  });
});