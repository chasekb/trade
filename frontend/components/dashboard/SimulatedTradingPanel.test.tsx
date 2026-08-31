/** @jest-environment jsdom */

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import SimulatedTradingPanel from './SimulatedTradingPanel';

const mockUseLiveTrading = jest.fn();
const mockUseOrderBookSignals = jest.fn();
const mockUseProducts = jest.fn();
const mockUseSimulatedTradingStats = jest.fn();
const mockUseSimulatedTradingDiagnosis = jest.fn();
const mockUseExecutionReconciliation = jest.fn();

jest.mock('@/hooks/useTrading', () => ({
  useLiveTrading: (...args: unknown[]) => mockUseLiveTrading(...args),
  useOrderBookSignals: (...args: unknown[]) => mockUseOrderBookSignals(...args),
  useProducts: (...args: unknown[]) => mockUseProducts(...args),
  useSimulatedTradingStats: (...args: unknown[]) => mockUseSimulatedTradingStats(...args),
  useSimulatedTradingDiagnosis: (...args: unknown[]) => mockUseSimulatedTradingDiagnosis(...args),
  useSimTradingWebSocket: jest.fn(),
}));
jest.mock('@/hooks/useExecutionReconciliation', () => ({
  useExecutionReconciliation: (...args: unknown[]) => mockUseExecutionReconciliation(...args),
}));
jest.mock('./OpenPositionsSection', () => ({ OpenPositionsSection: () => null }));
jest.mock('./RecentTradesTable', () => ({ RecentTradesTable: () => null }));
jest.mock('./StrategySelector', () => ({ StrategySelector: () => null }));
jest.mock('./TradingControls', () => ({ TradingControls: () => null }));
jest.mock('./StrategyConfigForm', () => ({ StrategyConfigForm: () => null }));
jest.mock('./OrderBookSignalsTable', () => ({ OrderBookSignalsTable: () => null }));
jest.mock('./ExecutionReconciliationTable', () => ({ ExecutionReconciliationTable: () => null }));

const activeStatus = {
  isActive: true,
  mode: 'simulated' as const,
  strategy: 'orderbook' as const,
  symbols: ['BTC-USD'],
  sessionId: 'session-1',
};

const emptyStats = {
  portfolio: {
    cash_balance: 10000,
    total_value: 10000,
    total_positions_value: 0,
    positions: [],
    trades: [],
    recent_trades: [],
  },
};

function renderPanel(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(
    <QueryClientProvider client={queryClient}>
      <SimulatedTradingPanel />
    </QueryClientProvider>,
  );
}

describe('SimulatedTradingPanel widget states', () => {
  beforeEach(() => {
    mockUseLiveTrading.mockReturnValue({
      status: activeStatus,
      startTrading: jest.fn(),
      stopTrading: jest.fn(),
      loading: false,
      updateStrategyParameters: jest.fn(),
    });
    mockUseProducts.mockReturnValue({ data: {} });
    mockUseSimulatedTradingDiagnosis.mockReturnValue({ data: undefined, error: null });
    mockUseExecutionReconciliation.mockReturnValue({ reconciliation: null, isLoading: false, error: null });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('shows distinct loading states for statistics and signals', () => {
    mockUseSimulatedTradingStats.mockReturnValue({ data: undefined, isLoading: true, error: null, refetch: jest.fn() });
    mockUseOrderBookSignals.mockReturnValue({ data: undefined, isLoading: true, isFetching: true, error: null, refetch: jest.fn() });

    renderPanel();

    expect(screen.getByText('Loading statistics...')).toBeInTheDocument();
    expect(screen.getByText('Loading order book signals...')).toBeInTheDocument();
  });

  it('shows visible request failures instead of rendering blank widgets', () => {
    mockUseSimulatedTradingStats.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('statistics unavailable'),
      refetch: jest.fn(),
    });
    mockUseOrderBookSignals.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('signals unavailable'),
      refetch: jest.fn(),
    });

    renderPanel();

    expect(screen.getByText('Failed to load statistics.')).toBeInTheDocument();
    expect(screen.getByText('Failed to load order book signals.')).toBeInTheDocument();
    expect(screen.getByText('signals unavailable')).toBeInTheDocument();
  });

  it('distinguishes an empty active session from a failed request', () => {
    mockUseSimulatedTradingStats.mockReturnValue({ data: emptyStats, isLoading: false, error: null, refetch: jest.fn() });
    mockUseOrderBookSignals.mockReturnValue({
      data: { signals: [], pagination: { total_pages: 0, total: 0, has_next: false, has_prev: false } },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: jest.fn(),
    });

    renderPanel();

    expect(screen.getByText(/No simulated trades have been recorded yet/)).toBeInTheDocument();
    expect(screen.getByText(/No order book signals are available/)).toBeInTheDocument();
    expect(screen.queryByText('Failed to load order book signals.')).not.toBeInTheDocument();
  });

  it('keeps per-symbol diagnosis visible when the latest signal page is empty', () => {
    mockUseSimulatedTradingStats.mockReturnValue({ data: emptyStats, isLoading: false, error: null, refetch: jest.fn() });
    mockUseOrderBookSignals.mockReturnValue({
      data: {
        signals: [],
        pagination: { total_pages: 0, total: 0, has_next: false, has_prev: false },
        diagnostics: {
          as_of: '2026-08-28T00:00:08.000Z',
          summary: {
            selected_count: 1,
            terminal_count: 1,
            trade_count: 0,
            outcome: 'no_trade',
            message: 'No trades recorded: TLS handshake failed (1).',
          },
          symbols: [{
            symbol: 'BTC-USD',
            updated_at: '2026-08-28T00:00:08.000Z',
            status: {
              primary: 'data_unavailable',
              terminal: true,
              reason: { code: 'tls_handshake', message: 'TLS handshake failed while contacting the market-data provider.' },
            },
          }],
        },
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: jest.fn(),
    });

    renderPanel();

    expect(screen.getByText('Per-symbol execution diagnosis')).toBeInTheDocument();
    expect(screen.getByText('data_unavailable')).toBeInTheDocument();
    expect(screen.getByText('TLS handshake failed while contacting the market-data provider.')).toBeInTheDocument();
    expect(screen.getByText(/No trades recorded: TLS handshake failed/)).toBeInTheDocument();
  });

  it('uses the canonical diagnosis query when signal loading fails', () => {
    mockUseSimulatedTradingStats.mockReturnValue({ data: emptyStats, isLoading: false, error: null, refetch: jest.fn() });
    mockUseOrderBookSignals.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error('signal request failed'),
      refetch: jest.fn(),
    });
    mockUseSimulatedTradingDiagnosis.mockReturnValue({
      data: {
        as_of: '2026-08-28T00:00:08.000Z',
        summary: { selected_count: 1, terminal_count: 1, trade_count: 0, outcome: 'no_trade', message: 'No trades recorded: valid HOLD.' },
        symbols: [{ symbol: 'BTC-USD', status: { primary: 'hold', terminal: true, reason: { code: 'signal_hold', message: 'Strategy returned HOLD.' } } }],
      },
      error: null,
    });

    renderPanel();

    expect(screen.getByText('Per-symbol execution diagnosis')).toBeInTheDocument();
    expect(screen.getByText('hold')).toBeInTheDocument();
    expect(screen.getByText('Strategy returned HOLD.')).toBeInTheDocument();
    expect(screen.getByText('Failed to load order book signals.')).toBeInTheDocument();
  });

  it('updates cash, positions, and total value together across the buy and sell trace', () => {
    const snapshots = [
      {
        portfolio: {
          cash_balance: 10000,
          current_capital: 999,
          total_positions_value: 0,
          total_value: 10000,
          positions: [],
          trades: [],
          recent_trades: [],
        },
      },
      {
        portfolio: {
          cash_balance: 9499.75,
          current_capital: 999,
          total_positions_value: 500,
          total_value: 9999.75,
          positions: [{ symbol: 'LONG-USD', side: 'buy', quantity: 5, current_price: 100 }],
          trades: [{ trade_id: 'buy-open', symbol: 'LONG-USD', side: 'buy', quantity: 5, price: 100, timestamp: '2026-06-18T10:00:00.000Z' }],
          recent_trades: [],
        },
      },
      {
        portfolio: {
          cash_balance: 10299.35,
          current_capital: 999,
          total_positions_value: -250,
          total_value: 10049.35,
          positions: [{ symbol: 'SHORT-USD', side: 'sell', quantity: 2, current_price: 125 }],
          trades: [{ trade_id: 'close-long', symbol: 'LONG-USD', side: 'sell', quantity: 5, price: 110, timestamp: '2026-06-18T10:01:00.000Z' }],
          recent_trades: [],
        },
      },
    ];
    let snapshotIndex = 0;
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    mockUseSimulatedTradingStats.mockImplementation(() => ({
      data: snapshots[snapshotIndex],
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    }));
    mockUseOrderBookSignals.mockReturnValue({
      data: { signals: [], pagination: { total_pages: 0, total: 0, has_next: false, has_prev: false } },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: jest.fn(),
    });

    const view = renderPanel(queryClient);
    const expectCards = (cash: string, total: string, positions: string) => {
      expect(screen.getByText('Cash Balance').parentElement).toHaveTextContent(cash);
      expect(screen.getByText('Total Value').parentElement).toHaveTextContent(total);
      expect(screen.getByText('Net Positions Value').parentElement).toHaveTextContent(positions);
    };

    expectCards('$10000.00', '$10000.00', '$0.00');

    snapshotIndex = 1;
    view.rerender(
      <QueryClientProvider client={queryClient}>
        <SimulatedTradingPanel />
      </QueryClientProvider>,
    );
    expectCards('$9499.75', '$9999.75', '$500.00');

    snapshotIndex = 2;
    view.rerender(
      <QueryClientProvider client={queryClient}>
        <SimulatedTradingPanel />
      </QueryClientProvider>,
    );
    expectCards('$10299.35', '$10049.35', '$-250.00');
  });
});
