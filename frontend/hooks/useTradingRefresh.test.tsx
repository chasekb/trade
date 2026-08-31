/** @jest-environment jsdom */

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { apiClient } from '@/lib/api';
import { normalizeTradingStatusPayload, useOrderBookSignals } from './useTrading';

jest.mock('@/lib/api', () => ({
  apiClient: {
    getOrderBookSignals: jest.fn(),
  },
}));

const getOrderBookSignals = apiClient.getOrderBookSignals as jest.Mock;

function signal(symbol: string) {
  return {
    symbol,
    timestamp: '2026-08-26T12:00:00Z',
    price: 100,
    signal: 'hold' as const,
    signal_generated: false,
    signal_strength: 0.5,
    data_status: 'sufficient' as const,
    spread: 0.01,
    volume: 100,
  };
}

describe('simulated trading status normalization', () => {
  it('unwraps backend status envelopes without losing active-session fields', () => {
    expect(normalizeTradingStatusPayload({
      status: 'success',
      data: {
        is_active: true,
        mode: 'simulated',
        strategy_type: 'ml_enhanced_orderbook',
        symbols: ['BTC-USD', 'ETH-USD'],
      },
    }, {
      isActive: false,
      mode: 'simulated',
      strategy: 'orderbook',
      symbols: [],
    })).toEqual({
      isActive: true,
      mode: 'simulated',
      strategy: 'ml_enhanced_orderbook',
      symbols: ['BTC-USD', 'ETH-USD'],
    });
  });

  it('uses the previous session values when a status payload omits optional fields', () => {
    expect(normalizeTradingStatusPayload({ status: 'active' }, {
      isActive: true,
      mode: 'simulated',
      strategy: 'orderbook',
      symbols: ['BTC-USD'],
    })).toEqual({
      isActive: true,
      mode: 'simulated',
      strategy: 'orderbook',
      symbols: ['BTC-USD'],
    });
  });

  it('does not turn a successful stop acknowledgement into an active session', () => {
    expect(normalizeTradingStatusPayload({ status: 'success', data: { message: 'stopped' } }, {
      isActive: false,
      mode: 'simulated',
      strategy: 'orderbook',
      symbols: [],
    }).isActive).toBe(false);
  });
});

describe('useOrderBookSignals refresh identity', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    getOrderBookSignals.mockResolvedValue({
      status: 'success',
      data: {
        signals: [signal('BTC-USD'), signal('ETH-USD')],
        pagination: { page: 1, limit: 10, total: 2, total_pages: 1, has_next: false, has_prev: false },
      },
    });
  });

  afterEach(() => {
    queryClient.clear();
    jest.clearAllMocks();
  });

  it('canonicalizes symbol-universe order so equivalent universes reuse one query', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { rerender } = renderHook(
      ({ symbols }: { symbols: string[] }) => useOrderBookSignals(symbols, true, 1, 10, 'orderbook', 'simulated'),
      { initialProps: { symbols: ['ETH-USD', 'BTC-USD'] }, wrapper },
    );

    await waitFor(() => expect(getOrderBookSignals).toHaveBeenCalledTimes(1));
    rerender({ symbols: ['BTC-USD', 'ETH-USD'] });
    await waitFor(() => expect(getOrderBookSignals).toHaveBeenCalledTimes(1));
    expect(getOrderBookSignals).toHaveBeenCalledWith(
      ['BTC-USD', 'ETH-USD'],
      { page: 1, per_page: 10 },
      'simulated',
    );
  });

  it('passes the active simulated session to signal queries', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    renderHook(
      () => useOrderBookSignals(['BTC-USD'], true, 1, 10, 'orderbook', 'simulated', 'session-1'),
      { wrapper },
    );

    await waitFor(() => expect(getOrderBookSignals).toHaveBeenCalledTimes(1));
    expect(getOrderBookSignals).toHaveBeenCalledWith(
      ['BTC-USD'],
      { page: 1, per_page: 10 },
      'simulated',
      'session-1',
    );
  });

  it('aggregates per-symbol diagnosis summaries across request chunks', async () => {
    const symbols = Array.from({ length: 51 }, (_, index) => `ASSET-${index}-USD`);
    getOrderBookSignals.mockImplementation(async (chunk: string[]) => ({
      status: 'success',
      data: {
        signals: chunk.map((symbol) => signal(symbol)),
        pagination: { page: 1, limit: chunk.length, total: chunk.length, total_pages: 1, has_next: false, has_prev: false },
        diagnostics: {
          selected_symbols: chunk,
          symbols: chunk.map((symbol) => ({
            symbol,
            status: { primary: 'hold', terminal: true },
          })),
          summary: {
            selected_count: chunk.length,
            terminal_count: chunk.length,
            trade_count: 2,
            by_primary_status: { hold: chunk.length },
            no_trade_reasons: [{ code: 'signal_hold', count: chunk.length }],
            message: 'No trades recorded: valid HOLD.',
          },
        },
      },
    }));
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(
      () => useOrderBookSignals(symbols, true, 1, 10, 'orderbook', 'simulated', 'session-1'),
      { wrapper },
    );

    await waitFor(() => expect(result.current.data?.diagnostics?.summary?.selected_count).toBe(51));
    expect(result.current.data?.diagnostics?.summary?.terminal_count).toBe(51);
    expect(result.current.data?.diagnostics?.summary?.trade_count).toBe(2);
    expect(result.current.data?.diagnostics?.summary?.by_primary_status?.hold).toBe(51);
    expect(result.current.data?.diagnostics?.summary?.no_trade_reasons).toEqual([
      { code: 'signal_hold', count: 51 },
    ]);
  });
});
