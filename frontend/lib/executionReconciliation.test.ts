import {
  formatBlockerMix,
  normalizeExecutionReconciliation,
  normalizeStrategyReconciliation,
  rankStrategiesByExpectancyRisk,
} from './executionReconciliation';

describe('normalizeExecutionReconciliation', () => {
  it('returns an empty snapshot for missing or malformed payloads', () => {
    for (const payload of [undefined, null, 'nope', 42]) {
      const snapshot = normalizeExecutionReconciliation(payload);
      expect(snapshot.byStrategy).toEqual([]);
      expect(snapshot.overall.strategy).toBe('overall');
      expect(snapshot.overall.signalsEvaluated).toBe(0);
      expect(snapshot.error).toBeNull();
    }
  });

  it('maps backend fields without rescaling win rate', () => {
    const snapshot = normalizeExecutionReconciliation({
      window_hours: 6,
      session_id: 'sess-1',
      trade_type: 'live_parity',
      signal_rows: 120,
      outcome_rows: 8,
      signal_rows_truncated: true,
      by_strategy: [
        {
          strategy: 'orderbook',
          signals_evaluated: 100,
          signals_generated: 40,
          executable_intents: 4,
          blocked_intents: 36,
          closing_legs: 4,
          winners: 1,
          losers: 3,
          win_rate: 25,
          average_win: 10,
          average_loss: 4,
          expectancy: -0.5,
          profit_factor: 0.83,
          total_pnl: -2,
          total_fees: 1.25,
          intent_conversion_rate: 0.1,
          outcome_coverage: 1,
          negative_expectancy_flag: true,
          dominant_blocker: 'spot_cannot_open_short',
          blockers: [
            { reason: 'insufficient_cash', count: 6, share: 6 / 36, blocked_expected_return_sum: 0.02 },
            { reason: 'spot_cannot_open_short', count: 30, share: 30 / 36, blocked_expected_return_sum: -0.05 },
          ],
        },
      ],
      overall: { strategy: 'overall', signals_evaluated: 100, win_rate: 25 },
    });

    expect(snapshot.windowHours).toBe(6);
    expect(snapshot.sessionId).toBe('sess-1');
    expect(snapshot.signalRowsTruncated).toBe(true);
    expect(snapshot.byStrategy).toHaveLength(1);

    const orderbook = snapshot.byStrategy[0];
    // 0-100 already; must not be multiplied again.
    expect(orderbook.winRate).toBe(25);
    expect(orderbook.averageLoss).toBe(4);
    expect(orderbook.expectancy).toBe(-0.5);
    expect(orderbook.negativeExpectancyFlag).toBe(true);
    expect(orderbook.blockers.map((b) => b.reason)).toEqual([
      'spot_cannot_open_short',
      'insufficient_cash',
    ]);
    expect(snapshot.overall.winRate).toBe(25);
  });

  it('keeps legitimate zeros instead of substituting fallbacks', () => {
    const row = normalizeStrategyReconciliation({
      strategy: 'rsi',
      win_rate: 0,
      expectancy: 0,
      total_pnl: 0,
      profit_factor: 0,
      intent_conversion_rate: 0,
    });
    expect(row.winRate).toBe(0);
    expect(row.expectancy).toBe(0);
    expect(row.totalPnl).toBe(0);
    expect(row.intentConversionRate).toBe(0);
  });

  it('derives blocker share when the backend omits it', () => {
    const row = normalizeStrategyReconciliation({
      strategy: 'orderbook',
      blocked_intents: 4,
      blockers: [{ reason: 'max_positions', count: 3 }, { reason: 'pending_order', count: 1 }],
    });
    expect(row.blockers[0].share).toBeCloseTo(0.75);
    expect(row.blockers[1].share).toBeCloseTo(0.25);
  });

  it('surfaces an undefined profit factor rather than a fabricated number', () => {
    const row = normalizeStrategyReconciliation({
      strategy: 'orderbook',
      profit_factor: 0,
      profit_factor_undefined: true,
    });
    expect(row.profitFactor).toBe(0);
    expect(row.profitFactorUndefined).toBe(true);
  });

  it('preserves a backend error string', () => {
    expect(normalizeExecutionReconciliation({ error: 'db down' }).error).toBe('db down');
    expect(normalizeExecutionReconciliation({ error: '' }).error).toBeNull();
  });

  it('drops malformed blocker rows', () => {
    const row = normalizeStrategyReconciliation({
      strategy: 'orderbook',
      blocked_intents: 1,
      blockers: [null, 'bad', { count: 1 }],
    });
    expect(row.blockers).toHaveLength(1);
    expect(row.blockers[0].reason).toBe('unknown');
  });
});

describe('rankStrategiesByExpectancyRisk', () => {
  it('puts the worst realized PnL first and breaks ties on blocked intents', () => {
    const snapshot = normalizeExecutionReconciliation({
      by_strategy: [
        { strategy: 'a', total_pnl: 5 },
        { strategy: 'b', total_pnl: -10 },
        { strategy: 'c', total_pnl: 0, blocked_intents: 2 },
        { strategy: 'd', total_pnl: 0, blocked_intents: 9 },
      ],
    });
    expect(rankStrategiesByExpectancyRisk(snapshot.byStrategy).map((s) => s.strategy)).toEqual([
      'b',
      'd',
      'c',
      'a',
    ]);
  });

  it('does not mutate the input array', () => {
    const input = normalizeExecutionReconciliation({
      by_strategy: [{ strategy: 'a', total_pnl: 5 }, { strategy: 'b', total_pnl: -1 }],
    }).byStrategy;
    const order = input.map((s) => s.strategy);
    rankStrategiesByExpectancyRisk(input);
    expect(input.map((s) => s.strategy)).toEqual(order);
  });
});

describe('formatBlockerMix', () => {
  it('renders counts with their share of blocked intents', () => {
    const row = normalizeStrategyReconciliation({
      strategy: 'orderbook',
      blocked_intents: 4,
      blockers: [{ reason: 'max_positions', count: 3 }, { reason: 'pending_order', count: 1 }],
    });
    expect(formatBlockerMix(row)).toBe('max_positions: 3 (75%), pending_order: 1 (25%)');
  });

  it('reports none when nothing was blocked', () => {
    expect(formatBlockerMix(normalizeStrategyReconciliation({ strategy: 'orderbook' }))).toBe('none');
  });
});
