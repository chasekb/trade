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

  it('never sends synthetic capital fields to a live Coinbase session', () => {
    const payload = buildStartTradingPayload(
      'orderbook',
      ['BTC-USD'],
      {
        initial_portfolio_size: 10000,
        initial_balance: 10000,
        capital: 10000,
        live_order_execution: true,
        position_size_mode: 'dollar',
        position_size_value: 10,
      },
      {},
      'live',
    );

    expect(payload.parameters.initial_portfolio_size).toBeUndefined();
    expect(payload.parameters.initial_balance).toBeUndefined();
    expect(payload.parameters.capital).toBeUndefined();
    expect(payload.initial_portfolio_size).toBeUndefined();
    expect(payload.initial_balance).toBeUndefined();
    expect(payload.capital).toBeUndefined();
    expect(payload.parameters.live_order_execution).toBe(true);
  });

  it('passes fee-aware order-book profitability controls through live parameters', () => {
    const payload = buildStartTradingPayload(
      'orderbook',
      ['ADA-USD'],
      {
        initial_portfolio_size: 10000,
        round_trip_fee_percent: 1.5,
        slippage_buffer_percent: 0.2,
        min_orderbook_signal_strength: 0.4,
      },
      {},
      'live',
    );

    expect(payload.parameters.round_trip_fee_percent).toBe(1.5);
    expect(payload.parameters.slippage_buffer_percent).toBe(0.2);
    expect(payload.parameters.min_orderbook_signal_strength).toBe(0.4);
  });

  it('passes ML-enhanced order-book risk caps and profitability controls through live parameters', () => {
    const payload = buildStartTradingPayload(
      'ml_enhanced_orderbook',
      ['BTC-USD'],
      {
        max_positions_per_session: 12,
        round_trip_fee_percent: 1.5,
        slippage_buffer_percent: 0.2,
        bid_ask_spread_threshold: 0.15,
        min_orderbook_signal_strength: 0.35,
        minimum_net_pnl_usd: 0.5,
      },
      { max_positions: 12 },
      'live',
    );

    expect(payload.max_positions).toBe(12);
    expect(payload.parameters.max_positions_per_session).toBe(12);
    expect(payload.parameters.round_trip_fee_percent).toBe(1.5);
    expect(payload.parameters.slippage_buffer_percent).toBe(0.2);
    expect(payload.parameters.bid_ask_spread_threshold).toBe(0.15);
    expect(payload.parameters.min_orderbook_signal_strength).toBe(0.35);
    expect(payload.parameters.minimum_net_pnl_usd).toBe(0.5);
  });

  it('preserves the explicit live-parity paper execution mode', () => {
    const payload = buildStartTradingPayload(
      'ml_enhanced_orderbook',
      ['BTC-USD', 'ETH-USD'],
      { execution_mode: 'live_parity', initial_portfolio_size: 10000 },
      { max_positions: 4 },
      'simulated',
    );

    expect(payload.parameters.execution_mode).toBe('live_parity');
    expect(payload.symbols).toEqual(['BTC-USD', 'ETH-USD']);
  });
});
