/** @jest-environment jsdom */

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import LiveTradingPanel from './LiveTradingPanel';

const mockUseLiveTrading = jest.fn();
const mockUseOrderBookSignals = jest.fn();
const mockUseProducts = jest.fn();
const mockUseLiveTabProducer = jest.fn();
const mockUseExecutionReconciliation = jest.fn();

jest.mock('@/hooks/useTrading', () => ({
  useLiveTrading: (...args: unknown[]) => mockUseLiveTrading(...args),
  useOrderBookSignals: (...args: unknown[]) => mockUseOrderBookSignals(...args),
  useProducts: (...args: unknown[]) => mockUseProducts(...args),
  useLiveTabProducer: (...args: unknown[]) => mockUseLiveTabProducer(...args),
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
jest.mock('./ManualTradeSection', () => ({ ManualTradeSection: () => null }));
jest.mock('./BotActivityLog', () => ({ BotActivityLog: () => null }));
jest.mock('./ExecutionReconciliationTable', () => ({ ExecutionReconciliationTable: () => null }));

const inactiveStatus = {
  isActive: false,
  mode: 'live' as const,
  strategy: 'ml_enhanced_orderbook' as const,
  symbols: [] as string[],
};

function positionsPortfolio(positions: Record<string, unknown>[]) {
  return {
    credentials_configured: true,
    account_snapshot_loaded: true,
    can_trade: true,
    is_active: false,
    cash_balance: 1000,
    total_value: 2000,
    total_positions_value: 1000,
    positions,
    stats: {},
  };
}

function renderPanel(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return render(
    <QueryClientProvider client={queryClient}>
      <LiveTradingPanel />
    </QueryClientProvider>,
  );
}

describe('LiveTradingPanel active positions stat', () => {
  beforeEach(() => {
    mockUseLiveTrading.mockReturnValue({
      status: inactiveStatus,
      startTrading: jest.fn(),
      stopTrading: jest.fn(),
      loading: false,
      updateStrategyParameters: jest.fn(),
      closePosition: jest.fn(),
      liquidateCoinbaseHoldings: jest.fn(),
    });
    mockUseOrderBookSignals.mockReturnValue({ data: undefined });
    mockUseProducts.mockReturnValue({ data: {} });
    mockUseExecutionReconciliation.mockReturnValue({ reconciliation: null, isLoading: false, error: null });
  });

  it('excludes unverified positions from the Active Positions count', () => {
    mockUseLiveTabProducer.mockReturnValue({
      data: positionsPortfolio([
        { symbol: 'BTC-USD', reconciliation_status: 'coinbase_confirmed' },
        { symbol: 'ETH-USD', reconciliation_status: 'pending_settlement' },
        { symbol: 'ADA-USD', reconciliation_status: 'unverified_missing_from_snapshot' },
        { symbol: 'SOL-USD', reconciliation_status: 'unverified_no_snapshot' },
      ]),
      isLoading: false,
      error: null,
    });

    renderPanel();

    const activePositionsLabel = screen.getByText('Active Positions');
    const tile = activePositionsLabel.parentElement;
    expect(tile).not.toBeNull();
    expect(tile!.querySelector('p.text-lg')).toHaveTextContent('2');
  });

  it('counts all positions when none are unverified', () => {
    mockUseLiveTabProducer.mockReturnValue({
      data: positionsPortfolio([
        { symbol: 'BTC-USD', reconciliation_status: 'coinbase_confirmed' },
        { symbol: 'ETH-USD', reconciliation_status: 'awaiting_snapshot_reconciliation' },
      ]),
      isLoading: false,
      error: null,
    });

    renderPanel();

    const activePositionsLabel = screen.getByText('Active Positions');
    const tile = activePositionsLabel.parentElement;
    expect(tile).not.toBeNull();
    expect(tile!.querySelector('p.text-lg')).toHaveTextContent('2');
  });
});
