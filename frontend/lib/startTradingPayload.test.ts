import { buildStartTradingPayload } from './api';

describe('buildStartTradingPayload', () => {
  it('sends strategy config under the canonical parameters key the backend reads', () => {
    const payload = buildStartTradingPayload(
      'rsi',
      ['BTC-USD'],
      {
        initial_portfolio_size: 25000,
        position_size_mode: 'dollar',
        position_size_value: 500,
        confidence_threshold: 0.7,
        fallback_to_baseline: 'false',
        window: 14,
        overbought: 70,
        oversold: 30,
      },
      { position_size_percent: 2, max_positions: 10, position_update_interval: 5 },
    );

    expect(payload.parameters.initial_portfolio_size).toBe(25000);
    expect(payload.parameters.position_size_mode).toBe('dollar');
    expect(payload.parameters.position_size_value).toBe(500);
    expect(payload.parameters.confidence_threshold).toBe(0.7);
    expect(payload.parameters.fallback_to_baseline).toBe('false');
    expect(payload.parameters.window).toBe(14);
    expect(payload.strategy).toBe('rsi');
    expect(payload.position_size_percent).toBe(2);
    expect(payload.max_positions).toBe(10);
  });

  it('derives initial_portfolio_size from capital when not set explicitly', () => {
    const payload = buildStartTradingPayload('orderbook', [], { capital: 5000 }, {});
    expect(payload.parameters.initial_portfolio_size).toBe(5000);
    expect(payload.initial_portfolio_size).toBe(5000);
    expect(payload.initial_balance).toBe(5000);
  });

  it('defaults initial_portfolio_size to 10000 when nothing is configured', () => {
    const payload = buildStartTradingPayload('sma', ['ETH-USD'], {}, {});
    expect(payload.parameters.initial_portfolio_size).toBe(10000);
  });
});
