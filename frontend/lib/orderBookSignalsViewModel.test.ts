import { buildOrderBookSignalRows, getOrderBookSignalCounts } from './orderBookSignalsViewModel';

const signal = (symbol: string, overrides: Record<string, unknown> = {}) => ({
  symbol,
  timestamp: '2026-09-01T12:00:00Z',
  price: 100,
  signal: 'hold' as const,
  signal_generated: false,
  signal_strength: 0,
  data_status: 'sufficient' as const,
  spread: 0.1,
  volume: 10,
  ...overrides,
});

describe('order book signal view model', () => {
  it('creates one discoverable row for every selected symbol and preserves pipeline outcomes', () => {
    const rows = buildOrderBookSignalRows({
      selectedSymbols: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD'],
      signals: [signal('BTC-USD', { signal: 'hold' }), signal('ETH-USD', { signal: 'buy', signal_generated: true })],
      diagnosis: {
        session_id: 'session-1',
        selected_symbols: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD'],
        symbols: [
          { symbol: 'BTC-USD', status: { primary: 'hold' }, signal: { side: 'buy' }, gates: { profitability: { blocked: true, reason: 'edge too low' } } },
          { symbol: 'ETH-USD', status: { primary: 'executable' }, intent: { executable: true } },
          { symbol: 'SOL-USD', status: { primary: 'quote_invalid', reason: { code: 'missing_quote', message: 'No quote returned' } } },
          { symbol: 'ADA-USD', status: { primary: 'transformer_not_ready' }, transformer: { state: 'warming_up' } },
          { symbol: 'DOT-USD', status: { primary: 'trade_completed' }, trade: { state: 'closed', realized_pnl: 2.5 } },
        ],
      },
    });

    expect(rows).toHaveLength(5);
    expect(rows.map((row) => row.symbol)).toEqual(['ADA-USD', 'BTC-USD', 'DOT-USD', 'ETH-USD', 'SOL-USD']);
    expect(rows.find((row) => row.symbol === 'BTC-USD')).toMatchObject({ outcome: 'hold', candidateSide: 'buy' });
    expect(rows.find((row) => row.symbol === 'ETH-USD')).toMatchObject({ outcome: 'executable' });
    expect(rows.find((row) => row.symbol === 'SOL-USD')).toMatchObject({ outcome: 'quote_invalid', blocker: 'missing_quote', reason: 'No quote returned' });
    expect(rows.find((row) => row.symbol === 'ADA-USD')).toMatchObject({ outcome: 'transformer_not_ready', modelState: 'warming_up' });
    expect(rows.find((row) => row.symbol === 'DOT-USD')).toMatchObject({ outcome: 'trade_completed', tradeState: 'closed' });
  });

  it('derives full-universe counts rather than visible-page counts', () => {
    const rows = buildOrderBookSignalRows({
      selectedSymbols: ['BTC-USD', 'ETH-USD', 'SOL-USD'],
      signals: [signal('BTC-USD')],
      diagnosis: {
        selected_symbols: ['BTC-USD', 'ETH-USD', 'SOL-USD'],
        symbols: [
          { symbol: 'BTC-USD', status: { primary: 'hold' } },
          { symbol: 'ETH-USD', status: { primary: 'gates_blocked' } },
          { symbol: 'SOL-USD', status: { primary: 'data_unavailable' } },
        ],
      },
    });

    expect(getOrderBookSignalCounts(rows)).toMatchObject({ total: 3, hold: 1, blocked: 1, unavailable: 1 });
  });
});
