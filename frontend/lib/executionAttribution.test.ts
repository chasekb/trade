import { normalizeAttributionRow, normalizeExecutionAttribution } from './executionAttribution';
import fixture from '../../tests/fixtures/execution_attribution_report.json';

describe('normalizeExecutionAttribution', () => {
  it('returns an empty report for missing or malformed payloads', () => {
    for (const payload of [undefined, null, 'nope', 42]) {
      const report = normalizeExecutionAttribution(payload);
      expect(report.byStrategy).toEqual([]);
      expect(report.byDiagnosticFactor).toEqual([]);
      expect(report.overall.key).toBe('overall');
      expect(report.overall.evaluated).toBe(0);
      expect(report.warning).toBeNull();
    }
  });

  it('maps the representative fixture without rescaling win rate', () => {
    const report = normalizeExecutionAttribution(fixture);

    expect(report.sessionId).toBe('sim_fixture');
    expect(report.tradeType).toBe('live_parity');
    expect(report.signalRows).toBe(5);
    expect(report.outcomeRows).toBe(3);
    expect(report.byStrategy).toHaveLength(1);

    const orderbook = report.byStrategy[0];
    expect(orderbook.key).toBe('orderbook');
    expect(orderbook.evaluated).toBe(5);
    expect(orderbook.explicitSkips).toBe(1);
    // Already a 0-100 percentage; must not be multiplied again.
    expect(orderbook.winRatePct).toBe(50);
    expect(orderbook.averageWinPnl).toBe(12);
    expect(orderbook.averageLossMagnitude).toBe(4);
    expect(orderbook.blockerCounts).toEqual({ pending_order: 1, spot_cannot_short: 1 });
    expect(orderbook.diagnosticFactorCounts).toEqual({
      account_or_exchange_blocker: 1,
      weak_strength: 1,
    });

    const bySymbol = orderbook.dimensions.by_symbol;
    expect(bySymbol['BTC-USD'].winRatePct).toBe(100);
    expect(bySymbol['ETH-USD'].averageRealizedPnl).toBe(-4);

    // The strength-bucket dimension has signal-side counts but no outcome
    // linkage; its win rate must stay null, never a coerced zero.
    const byStrength = orderbook.dimensions.by_strength_bucket;
    expect(byStrength.strong.evaluated).toBe(1);
    expect(byStrength.strong.winRatePct).toBeNull();
    expect(byStrength.strong.averageRealizedPnl).toBeNull();

    expect(report.byDiagnosticFactor).toHaveLength(2);
    const weakStrength = report.byDiagnosticFactor.find((row) => row.key === 'weak_strength');
    expect(weakStrength?.insufficientData).toBe(true);
    expect(weakStrength?.winRatePct).toBeNull();

    expect(report.overall.winRatePct).toBe(50);
    expect(report.overall.pnlPopulation).toBe(2);
  });

  it('keeps a legitimate zero win rate instead of substituting null', () => {
    const row = normalizeAttributionRow({
      strategy: 'rsi',
      win_count: 0,
      loss_count: 3,
      win_rate_pct: 0,
      average_realized_pnl: -2,
    });
    expect(row.winRatePct).toBe(0);
    expect(row.averageRealizedPnl).toBe(-2);
  });

  it('normalizes a missing win rate to null rather than 0', () => {
    const row = normalizeAttributionRow({ strategy: 'rsi', win_rate_pct: null });
    expect(row.winRatePct).toBeNull();
  });

  it('prefers the factor field for diagnostic-factor rows', () => {
    const row = normalizeAttributionRow({ factor: 'missing_expected_return', evaluated: 3 });
    expect(row.key).toBe('missing_expected_return');
    expect(row.evaluated).toBe(3);
  });

  it('preserves a backend warning string', () => {
    expect(normalizeExecutionAttribution({ warning: 'no data' }).warning).toBe('no data');
    expect(normalizeExecutionAttribution({ warning: '' }).warning).toBeNull();
  });
});
