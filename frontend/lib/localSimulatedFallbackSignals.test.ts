describe('local simulated fallback order-book signal contract', () => {
  const loadApi = async () => {
    jest.resetModules();
    process.env.NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING = 'true';
    return import('./api');
  };

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_FORCE_LOCAL_SIM_TRADING;
    jest.resetModules();
  });

  it('separates ml_enhanced_orderbook strategy metadata from signal fields', async () => {
    const { apiClient } = await loadApi();

    await apiClient.startTrading('simulated', 'ml_enhanced_orderbook', ['BTC-USD', 'ETH-USD'], {}, {});
    const response = await apiClient.getOrderBookSignals(undefined, { page: 1, per_page: 10 }, 'simulated');

    expect(response.status).toBe('success');
    expect(response.data?.signals).toHaveLength(2);
    for (const signal of response.data?.signals ?? []) {
      expect(['buy', 'sell', 'hold']).toContain(signal.signal_type);
      expect(signal.signal_type).toBe(signal.signal);
      expect(['BUY', 'SELL', 'HOLD']).toContain(signal.prediction);
      expect(signal.signal_type).not.toBe('ml_enhanced_orderbook');
      expect(signal.ml_analysis?.analytics?.strategy).toBe('ml_enhanced_orderbook');
    }
  });

  it('separates non-orderbook strategy metadata from signal fields', async () => {
    const { apiClient } = await loadApi();

    await apiClient.startTrading('simulated', 'rsi', ['SOL-USD'], {}, {});
    const response = await apiClient.getOrderBookSignals(undefined, { page: 1, per_page: 10 }, 'simulated');

    expect(response.status).toBe('success');
    const [signal] = response.data?.signals ?? [];
    expect(signal).toBeDefined();
    expect(['buy', 'sell', 'hold']).toContain(signal.signal_type);
    expect(signal.signal_type).toBe(signal.signal);
    expect(signal.signal_type).not.toBe('rsi');
    expect(signal.ml_analysis?.analytics?.strategy).toBe('rsi');
    expect(signal.ml_analysis?.expected_return_available).toBe(false);
    expect(signal.ml_analysis?.diagnostic_factor).toBe('expected_return_unavailable');
    expect(signal.ml_analysis?.factoring_semantics).toBe('unavailable');
    expect(signal.ml_analysis?.profitability_gate_passed).toBe(false);
    expect(signal.ml_analysis?.profitability_gate_reason).toBe('Expected-return diagnostic is unavailable');
  });
});
