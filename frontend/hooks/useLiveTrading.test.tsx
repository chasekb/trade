/** @jest-environment jsdom */

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import { apiClient } from '@/lib/api';
import { useLiveTrading } from './useTrading';

jest.mock('@/lib/api', () => ({
  apiClient: {
    getTradingStatus: jest.fn(),
    startTrading: jest.fn(),
  },
}));

const getTradingStatus = apiClient.getTradingStatus as jest.Mock;
const startTrading = apiClient.startTrading as jest.Mock;

describe('useLiveTrading start mutation', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    jest.clearAllMocks();
    getTradingStatus.mockResolvedValue({ status: 'success', data: { is_active: false } });
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  });

  function wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  // A previous session that hasn't finished flushing pending orders/writes yet
  // returns HTTP 200 with status:'settling' rather than starting a new one.
  // Before this fix, only status:'error' was treated as a failure, so this
  // response was silently swallowed: the button reverted to "Start Trading"
  // with no error shown and no session actually started.
  it('rejects when the backend reports a settling session instead of silently no-opping', async () => {
    startTrading.mockResolvedValue({
      status: 'settling',
      error: 'The previous session is still settling orders or persistence writes',
    });

    const { result } = renderHook(() => useLiveTrading('simulated'), { wrapper });

    await expect(
      result.current.startTrading({
        mode: 'simulated',
        strategy: 'ml_enhanced_orderbook',
        symbols: ['BTC-USD'],
        parameters: {},
      } as Parameters<typeof result.current.startTrading>[0])
    ).rejects.toThrow('still settling orders');
  });

  it('still resolves for a genuinely started session', async () => {
    startTrading.mockResolvedValue({
      status: 'success',
      is_active: true,
      session_id: 'session-1',
    });

    const { result } = renderHook(() => useLiveTrading('simulated'), { wrapper });

    await act(async () => {
      await result.current.startTrading({
        mode: 'simulated',
        strategy: 'ml_enhanced_orderbook',
        symbols: ['BTC-USD'],
        parameters: {},
      } as Parameters<typeof result.current.startTrading>[0]);
    });
  });
});
