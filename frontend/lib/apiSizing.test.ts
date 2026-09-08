import { calculateLocalAllocatedUsd, minimumTradeSizeDecision } from './api';

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

describe('minimumTradeSizeDecision', () => {
  it('allows expected-return trades that clear fees, slippage, spread, and cap', () => {
    const decision = minimumTradeSizeDecision({
      price: 100,
      expectedReturnFraction: 0.03,
      roundTripFeeFraction: 0.0016,
      slippageBufferFraction: 0.002,
      spreadFraction: 0.001,
      minimumNetPnlUsd: 1,
      configuredMaxNotionalUsd: 100,
    });

    expect(decision.shouldTrade).toBe(true);
    expect(decision.notionalUsd).toBeLessThanOrEqual(100);
    expect(decision.quantity).toBeGreaterThan(0);
  });

  it('blocks zero or negative edge after profitability hurdles', () => {
    const decision = minimumTradeSizeDecision({
      price: 100,
      expectedReturnFraction: 0.002,
      roundTripFeeFraction: 0.0016,
      slippageBufferFraction: 0.002,
      spreadFraction: 0.001,
      minimumNetPnlUsd: 0,
      configuredMaxNotionalUsd: 100,
    });

    expect(decision.shouldTrade).toBe(false);
  });

  it('blocks trades whose configured cap is below the minimum profitable notional', () => {
    const decision = minimumTradeSizeDecision({
      price: 0.45,
      expectedReturnFraction: 0.03,
      roundTripFeeFraction: 0.0016,
      slippageBufferFraction: 0.002,
      spreadFraction: 0.001,
      minimumNetPnlUsd: 10,
      configuredMaxNotionalUsd: 50,
    });

    expect(decision.shouldTrade).toBe(false);
  });

  it('keeps an explicit override for intentionally unprofitable simulations', () => {
    const decision = minimumTradeSizeDecision({
      price: 100,
      expectedReturnFraction: -0.01,
      roundTripFeeFraction: 0.0016,
      slippageBufferFraction: 0.002,
      spreadFraction: 0.001,
      minimumNetPnlUsd: 0,
      configuredMaxNotionalUsd: 100,
      allowUnprofitableTrades: true,
    });

    expect(decision.shouldTrade).toBe(true);
    expect(decision.notionalUsd).toBe(100);
  });
});