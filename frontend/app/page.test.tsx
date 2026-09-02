/** @jest-environment jsdom */

import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import Dashboard from './page';

let mockLiveShouldThrow = false;
let mockSimulatedShouldThrow = false;

jest.mock('@/components/dashboard/TradingStatisticsDashboard', () => ({
  TradingStatisticsDashboard: () => <div>Overview panel</div>,
}));

jest.mock('@/components/dashboard/LiveTradingPanel', () => ({
  __esModule: true,
  default: () => {
    if (mockLiveShouldThrow) {
      throw new Error('Live panel render failure');
    }
    return <div>Live panel content</div>;
  },
}));

jest.mock('@/components/dashboard/SimulatedTradingPanel', () => ({
  __esModule: true,
  default: () => {
    if (mockSimulatedShouldThrow) {
      throw new Error('Simulated panel render failure');
    }
    return <div>Simulated panel content</div>;
  },
}));

jest.mock('@/components/dashboard/BacktestingPanel', () => ({
  __esModule: true,
  default: () => <div>Backtesting panel</div>,
}));

jest.mock('@/components/dashboard/MLAnalyticsDashboard', () => ({
  __esModule: true,
  default: () => <div>ML analytics panel</div>,
}));

jest.mock('@/components/dashboard/PositionsTable', () => ({
  PositionsTable: () => <div>Positions panel</div>,
}));

describe('Dashboard tab error isolation', () => {
  const originalConsoleError = console.error;

  beforeEach(() => {
    mockLiveShouldThrow = false;
    mockSimulatedShouldThrow = false;
    console.error = jest.fn();
  });

  afterEach(() => {
    console.error = originalConsoleError;
  });

  it('shows a visible Live Trading tab fallback and keeps other tabs usable after a render crash', () => {
    mockLiveShouldThrow = true;

    render(<Dashboard />);
    fireEvent.click(screen.getByRole('button', { name: /Live Trading/ }));

    expect(screen.getByRole('alert')).toHaveTextContent('Live Trading tab failed to render');
    expect(screen.getByText('Live panel render failure')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Simulated Trading/ }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText('Simulated panel content')).toBeInTheDocument();
  });

  it('shows a visible Simulated Trading tab fallback and keeps other tabs usable after a render crash', () => {
    mockSimulatedShouldThrow = true;

    render(<Dashboard />);
    fireEvent.click(screen.getByRole('button', { name: /Simulated Trading/ }));

    expect(screen.getByRole('alert')).toHaveTextContent('Simulated Trading tab failed to render');
    expect(screen.getByText('Simulated panel render failure')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Live Trading/ }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText('Live panel content')).toBeInTheDocument();
  });
});
