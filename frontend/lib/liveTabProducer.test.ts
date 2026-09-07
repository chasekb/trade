import { normalizeLiveTabProducerSnapshot } from './liveTabProducer';

describe('normalizeLiveTabProducerSnapshot', () => {
  it('uses Coinbase portfolio fields as the live tab source of truth', () => {
    const snapshot = normalizeLiveTabProducerSnapshot({
      source: 'coinbase',
      is_active: true,
      can_trade: true,
      live_order_execution_enabled: true,
      credentials_configured: true,
      account_snapshot_loaded: true,
      portfolio: {
        cash_balance: 125.5,
        cash_hold: 4.5,
        total_positions_value: 250,
        total_value: 380,
        holdings: [{ asset: 'BTC', available: 0.001, hold: 0.0001, price_usd: 65000 }],
      },
      positions: [{ symbol: 'BTC-USD', quantity: 0.0011, current_price: 65000 }],
      pending_orders: [{ product_id: 'ETH-USD', side: 'buy' }],
      readiness: {
        can_trade: true,
        blockers: [],
      },
    });

    expect(snapshot.source).toBe('coinbase');
    expect(snapshot.cashBalance).toBe(125.5);
    expect(snapshot.cashHold).toBe(4.5);
    expect(snapshot.totalPositionsValue).toBe(250);
    expect(snapshot.totalValue).toBe(380);
    expect(snapshot.holdings).toHaveLength(1);
    expect(snapshot.positions).toHaveLength(1);
    expect(snapshot.pendingOrders).toHaveLength(1);
    expect(snapshot.canTrade).toBe(true);
    expect(snapshot.blockers).toEqual([]);
  });

  it('keeps the live tab disabled and surfaces producer blockers when Coinbase is not ready', () => {
    const snapshot = normalizeLiveTabProducerSnapshot({
      status: 'success',
      source: 'coinbase',
      is_active: false,
      can_trade: false,
      live_order_execution_enabled: false,
      credentials_configured: false,
      account_snapshot_loaded: false,
      errors: ['Coinbase credentials are not configured'],
      readiness: {
        can_trade: false,
        blockers: [
          'Coinbase credentials are not configured',
          'Live order execution must be explicitly confirmed',
        ],
      },
    });

    expect(snapshot.canTrade).toBe(false);
    expect(snapshot.credentialsConfigured).toBe(false);
    expect(snapshot.accountSnapshotLoaded).toBe(false);
    expect(snapshot.liveOrderExecutionEnabled).toBe(false);
    expect(snapshot.blockers).toEqual([
      'Coinbase credentials are not configured',
      'Live order execution must be explicitly confirmed',
    ]);
    expect(snapshot.errors).toEqual(['Coinbase credentials are not configured']);
  });
});
