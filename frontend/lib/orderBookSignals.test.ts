import {
  mergeNormalizedOrderBookSignals,
  normalizeOrderBookSignalsResponse,
} from './orderBookSignals';

const signal = (symbol: string, strength = 0.5) => ({
  symbol,
  timestamp: '2026-08-22T12:00:00.000Z',
  price: 100,
  signal: 'hold' as const,
  signal_generated: false,
  signal_strength: strength,
  data_status: 'sufficient' as const,
  spread: 0.1,
  volume: 10,
});

describe('order-book signal response normalization', () => {
  it('normalizes legacy field names without changing server totals', () => {
    const result = normalizeOrderBookSignalsResponse({
      signals: [signal('BTC-USD')],
      pagination: {
        current_page: 2,
        per_page: 25,
        total_signals: 51,
        total_pages: 3,
        has_next: true,
        has_prev: true,
      },
      total_analyzed: 90,
      active_signals: 4,
      average_strength: 0.5,
    }, 'live');

    expect(result.pagination).toEqual({ page: 2, limit: 25, total: 51, totalPages: 3, hasNext: true, hasPrev: true });
    expect(result.summary.totalAnalyzed).toBe(90);
    expect(result.summary.activeSignals).toBe(4);
    expect(result.deviations.unavailableFields).toEqual([]);
  });

  it('does not fabricate missing totals or active counts', () => {
    const result = normalizeOrderBookSignalsResponse({ signals: [signal('ETH-USD')] }, 'simulated');

    expect(result.signals).toHaveLength(1);
    expect(result.pagination.total).toBeUndefined();
    expect(result.summary.activeSignals).toBeUndefined();
    expect(result.deviations.unavailableFields).toEqual([
      'total analyzed',
      'active signals',
      'pagination total',
      'pagination total pages',
    ]);
  });

  it('preserves zero values and exposes live blockers as a deviation', () => {
    const result = normalizeOrderBookSignalsResponse({
      signals: [{ ...signal('SOL-USD'), execution_analysis: { blocked: true, blocker_reason: 'spot-only sell' } }],
      total_analyzed: 0,
      active_signals: 0,
      pagination: { total: 0, total_pages: 0 },
    }, 'live');

    expect(result.summary.totalAnalyzed).toBe(0);
    expect(result.summary.activeSignals).toBe(0);
    expect(result.deviations.liveExecutionBlockersVisible).toBe(true);
  });

  it('merges chunk responses while retaining unavailable metadata explicitly', () => {
    const result = mergeNormalizedOrderBookSignals([
      normalizeOrderBookSignalsResponse({ signals: [signal('BTC-USD', 0.9)], pagination: { total: 1, total_pages: 1 }, total_analyzed: 1, active_signals: 1 }, 'simulated'),
      normalizeOrderBookSignalsResponse({ signals: [signal('ETH-USD', 0.8)], pagination: { total: 1, total_pages: 1 }, total_analyzed: 1 }, 'simulated'),
    ], 1, 10);

    expect(result.pagination.total).toBe(2);
    expect(result.summary.totalAnalyzed).toBe(2);
    expect(result.summary.activeSignals).toBeUndefined();
    expect(result.signals.map(({ symbol }) => symbol)).toEqual(['BTC-USD', 'ETH-USD']);
  });
});
