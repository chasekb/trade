/** @jest-environment jsdom */

import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { OrderBookSignalsTable } from '../OrderBookSignalsTable';

function signal(symbol: string, timestamp: string) {
  return {
    symbol,
    timestamp,
    price: 100,
    signal: 'hold' as const,
    signal_generated: false,
    signal_strength: 0.5,
    data_status: 'sufficient' as const,
    spread: 0.01,
    volume: 10,
  };
}

test('renders a large selected universe and delayed-row timestamp without blocking valid symbols', () => {
  const timestamp = '2026-09-01T17:22:18.100Z';
  const selectedSymbols = Array.from({ length: 257 }, (_, index) => `ASSET-${index}-USD`);

  render(
    <OrderBookSignalsTable
      signals={[signal('ASSET-0-USD', timestamp)]}
      selectedSymbols={selectedSymbols}
      currentPage={1}
      pageSize={257}
    />,
  );

  const row = screen.getByRole('row', { name: /ASSET-0-USD/ });
  expect(within(row).getByText(new Date(timestamp).toLocaleString())).toBeInTheDocument();
  expect(screen.getByText('ASSET-256-USD')).toBeInTheDocument();
  expect(screen.getByText(/Showing 257 of 257 matching rows/)).toBeInTheDocument();
});
