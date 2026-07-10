import { normalizeSimulatedTradingSnapshot } from './simulatedTradingStats';

describe('normalizeSimulatedTradingSnapshot', () => {
  it('prefers backend stats when they are present', () => {
    const snapshot = normalizeSimulatedTradingSnapshot({
      portfolio: {
        cash_balance: 1250,
        unrealized_pnl: 75,
        realized_pnl: 25,
        total_fees: 12.5,
        total_value: 1400,
        total_positions_value: 150,
        open_positions_count: 2,
        positions: {
          BTC: { symbol: 'BTC', quantity: 1, entry_price: 100, current_price: 110 },
        },
        recent_trades: [{ trade_id: 'portfolio-trade', symbol: 'BTC', side: 'buy', quantity: 1, price: 100, pnl: 3, timestamp: '2026-06-18T12:00:00.000Z' }],
        trades: [{ trade_id: 'portfolio-trade', symbol: 'BTC', side: 'buy', quantity: 1, price: 100, pnl: 3, timestamp: '2026-06-18T12:00:00.000Z' }],
      },
      stats: {
        total_pnl: 9,
        total_fees: 1.5,
        net_pnl: 7.5,
        win_rate: 55,
        total_trades: 4,
        winning_trades: 2,
        losing_trades: 1,
        avg_win: 6,
        avg_loss: -4,
        best_trade: 10,
        worst_trade: -8,
        profit_factor: 2.5,
        sharpe_ratio: 1.25,
        max_drawdown: 3,
        total_volume: 420,
        avg_trade_size: 105,
        trades_today: 1,
        last_trade_time: '2026-06-18T12:00:00.000Z',
      },
    });

    expect(snapshot.stats.total_trades).toBe(4);
    expect(snapshot.stats.win_rate).toBe(55);
    expect(snapshot.stats.avg_win).toBe(6);
    expect(snapshot.stats.last_trade_time).toBe('2026-06-18T12:00:00.000Z');
    expect(snapshot.cashBalance).toBe(1250);
    expect(snapshot.totalValue).toBe(1400);
    expect(snapshot.totalPositionsValue).toBe(150);
    expect(snapshot.activePositions).toBe(2);
    expect(snapshot.recentTrades).toHaveLength(1);
  });

  it('derives stats from trades when backend stats are absent', () => {
    const snapshot = normalizeSimulatedTradingSnapshot({
      current_capital: 1010,
      unrealized_pnl: 40,
      realized_pnl: 10,
      total_fees: 5,
      positions: [],
      recent_trades: [
        {
          trade_id: 'trade-2',
          symbol: 'ETH-USD',
          side: 'sell',
          quantity: 2,
          price: 120,
          pnl: -6,
          fees: 1,
          timestamp: '2026-06-18T14:00:00.000Z',
        },
      ],
      trades: [
        {
          trade_id: 'trade-1',
          symbol: 'BTC-USD',
          side: 'buy',
          quantity: 1,
          price: 100,
          pnl: 10,
          fees: 2,
          timestamp: '2026-06-18T13:00:00.000Z',
        },
        {
          trade_id: 'trade-2',
          symbol: 'ETH-USD',
          side: 'sell',
          quantity: 2,
          price: 120,
          pnl: -6,
          fees: 1,
          timestamp: '2026-06-18T14:00:00.000Z',
        },
      ],
    });

    expect(snapshot.stats.total_trades).toBe(2);
    expect(snapshot.stats.winning_trades).toBe(1);
    expect(snapshot.stats.losing_trades).toBe(1);
    expect(snapshot.stats.win_rate).toBe(50);
    expect(snapshot.stats.total_volume).toBe(340);
    expect(snapshot.stats.avg_trade_size).toBe(170);
    expect(snapshot.stats.best_trade).toBe(10);
    expect(snapshot.stats.worst_trade).toBe(-6);
    expect(snapshot.stats.max_drawdown).toBe(6);
    // The snapshot-level total_fees (5) already includes per-trade fees; the
    // derived stats must not add the per-trade fees on top of it.
    expect(snapshot.stats.total_fees).toBe(5);
    expect(snapshot.stats.net_pnl).toBe(-1);
    expect(snapshot.stats.last_trade_time).toBe('2026-06-18T14:00:00.000Z');
    expect(snapshot.recentTrades.map((trade) => trade.trade_id)).toEqual(['trade-2', 'trade-1']);
  });

  it('keeps open-leg trades out of win-rate calculations while still counting them toward totals', () => {
    const snapshot = normalizeSimulatedTradingSnapshot({
      portfolio: {
        cash_balance: 1000,
        realized_pnl: 4,
        unrealized_pnl: 6,
        total_fees: 3.5,
        recent_trades: [
          {
            trade_id: 'trade-open',
            symbol: 'BTC-USD',
            side: 'buy',
            quantity: 1,
            price: 50,
            pnl: 0,
            fees: 0.5,
            timestamp: '2026-06-18T12:00:00.000Z',
          },
          {
            trade_id: 'trade-win',
            symbol: 'BTC-USD',
            side: 'sell',
            quantity: 1,
            price: 100,
            pnl: 10,
            fees: 2,
            timestamp: '2026-06-18T13:00:00.000Z',
          },
          {
            trade_id: 'trade-loss',
            symbol: 'ETH-USD',
            side: 'buy',
            quantity: 2,
            price: 120,
            pnl: -6,
            fees: 1,
            timestamp: '2026-06-18T14:00:00.000Z',
          },
        ],
      },
    });

    expect(snapshot.stats.total_trades).toBe(3);
    expect(snapshot.stats.winning_trades).toBe(1);
    expect(snapshot.stats.losing_trades).toBe(1);
    expect(snapshot.stats.win_rate).toBe(50);
    expect(snapshot.stats.total_fees).toBe(3.5);
    expect(snapshot.stats.total_volume).toBe(390);
    expect(snapshot.stats.avg_trade_size).toBe(130);
  });

  it('sums per-trade fees only when no portfolio-level fee total is provided', () => {
    const snapshot = normalizeSimulatedTradingSnapshot({
      portfolio: {
        cash_balance: 1000,
        recent_trades: [
          {
            trade_id: 'trade-win',
            symbol: 'BTC-USD',
            side: 'sell',
            quantity: 1,
            price: 100,
            pnl: 10,
            fees: 2,
            timestamp: '2026-06-18T13:00:00.000Z',
          },
          {
            trade_id: 'trade-loss',
            symbol: 'ETH-USD',
            side: 'sell',
            quantity: 2,
            price: 120,
            pnl: -6,
            fees: 1,
            timestamp: '2026-06-18T14:00:00.000Z',
          },
        ],
      },
    });

    expect(snapshot.stats.total_fees).toBe(3);
    expect(snapshot.stats.net_pnl).toBe(1);
    expect(snapshot.stats.last_trade_time).toBe('2026-06-18T14:00:00.000Z');
  });

  it('reports the latest trade time even when trades arrive unsorted', () => {
    const snapshot = normalizeSimulatedTradingSnapshot({
      portfolio: {
        recent_trades: [
          { trade_id: 'later', symbol: 'BTC-USD', side: 'sell', pnl: 1, timestamp: '2026-06-18T15:00:00.000Z' },
          { trade_id: 'earlier', symbol: 'BTC-USD', side: 'buy', pnl: 0, timestamp: '2026-06-18T09:00:00.000Z' },
        ],
      },
    });

    expect(snapshot.stats.last_trade_time).toBe('2026-06-18T15:00:00.000Z');
  });
});
