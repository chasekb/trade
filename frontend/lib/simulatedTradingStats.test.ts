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
    expect(snapshot.stats.total_fees).toBe(8);
    expect(snapshot.stats.net_pnl).toBe(-4);
    expect(snapshot.stats.last_trade_time).toBe('2026-06-18T14:00:00.000Z');
    expect(snapshot.recentTrades.map((trade) => trade.trade_id)).toEqual(['trade-2', 'trade-1']);
  });
});
