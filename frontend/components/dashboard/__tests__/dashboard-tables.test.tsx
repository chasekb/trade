/** @jest-environment jsdom */

import React from 'react';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import { OpenPositionsSection } from '../OpenPositionsSection';
import { RecentTradesTable } from '../RecentTradesTable';
import { OrderBookSignalsTable } from '../OrderBookSignalsTable';

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

describe('trade dashboard tables', () => {
  it('renders open positions values and columns', () => {
    render(
      <OpenPositionsSection
        positions={[{ symbol: 'BTC-USD', side: 'long', quantity: 1.5, entry_price: 100, current_price: 125, unrealized_pnl: 37.5, entry_time: '2026-07-06T12:00:00Z' }]}
      />
    );

    expect(screen.getByText('Open Positions')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Symbol' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Side' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Quantity' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Entry' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Current' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Unrealized P&L' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Management' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Opened' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Action' })).toBeInTheDocument();

    const row = screen.getByRole('row', { name: /BTC-USD/ });
    expect(within(row).getByText('BTC-USD')).toBeInTheDocument();
    expect(within(row).getByText('LONG')).toBeInTheDocument();
    expect(within(row).getByText('1.5000')).toBeInTheDocument();
    expect(within(row).getByText('$100.0000')).toBeInTheDocument();
    expect(within(row).getByText('$125.0000')).toBeInTheDocument();
    expect(within(row).getByText('$37.50')).toBeInTheDocument();
    expect(within(row).getByText('Session-managed')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('labels account-managed Coinbase holdings distinctly from session positions', () => {
    render(<OpenPositionsSection positions={[{ symbol: 'ETH-USD', side: 'buy', quantity: 0.25, entry_price: 3500, current_price: 3510, unrealized_pnl: 0, entry_time: '2026-07-06T12:00:00Z', session_managed: true, inherited_quantity: 0.25, management_state: 'account_managed' }]} onClose={jest.fn()} />);
    const row = screen.getByRole('row', { name: /ETH-USD/ });
    expect(within(row).getByText('Account-managed')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('renders explicit liquidation controls for Coinbase-only holdings', async () => {
    const liquidateHolding = jest.fn();
    const liquidateAll = jest.fn();
    render(<OpenPositionsSection positions={[{ symbol: 'ADA-USD', side: 'long', quantity: 25, entry_price: 0.5, current_price: 0.51, unrealized_pnl: 0, entry_time: '2026-07-06T12:00:00Z', session_managed: false }]} onClose={jest.fn()} onLiquidateHolding={liquidateHolding} onLiquidateAllHoldings={liquidateAll} />);

    fireEvent.click(screen.getByRole('button', { name: 'Liquidate holding' }));
    await waitFor(() => expect(liquidateHolding).toHaveBeenCalledWith('ADA-USD'));
    fireEvent.click(screen.getByRole('button', { name: /Liquidate all Coinbase holdings/ }));
    await waitFor(() => expect(liquidateAll).toHaveBeenCalled());
  });

  it('renders recent trades values and optional fees column', () => {
    render(<RecentTradesTable includeFees trades={[{ timestamp: '2026-07-06T12:30:00Z', symbol: 'ETH-USD', side: 'buy', quantity: 2, price: 2500, fees: 3.25, pnl: 125.5 }]} />);
    expect(screen.getByText('Recent Trades')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Fees' })).toBeInTheDocument();
    const row = screen.getByRole('row', { name: /ETH-USD/ });
    expect(within(row).getByText('ETH-USD')).toBeInTheDocument();
    expect(within(row).getByText('BUY')).toBeInTheDocument();
    expect(within(row).getByText('2.0000')).toBeInTheDocument();
    expect(within(row).getByText('$2500.00')).toBeInTheDocument();
    expect(within(row).getByText('$3.25')).toBeInTheDocument();
    expect(within(row).getByText('125.50')).toBeInTheDocument();
  });

  it('keeps every selected symbol and pipeline outcome visible across the full universe', () => {
    render(
      <OrderBookSignalsTable
        selectedSymbols={['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD']}
        signals={[signal('BTC-USD')]}
        diagnosis={{
          selected_symbols: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD'],
          symbols: [
            { symbol: 'BTC-USD', status: { primary: 'hold' } },
            { symbol: 'ETH-USD', status: { primary: 'executable' }, intent: { executable: true } },
            { symbol: 'SOL-USD', status: { primary: 'quote_invalid', reason: { code: 'missing_quote', message: 'No quote returned' } } },
            { symbol: 'ADA-USD', status: { primary: 'transformer_not_ready' }, transformer: { state: 'warming_up' } },
            { symbol: 'DOT-USD', status: { primary: 'trade_completed' }, trade: { state: 'closed', realized_pnl: 2.5 } },
          ],
          summary: {
            stage_counts: {
              selected_symbols: 5,
              quote_success_evaluations: 4,
              quote_failures: 1,
              transformer_ready_evaluations: 3,
              transformer_warmup_events: 1,
              signal_holds: 1,
              generated_candidates: 1,
              profitability_gate_passed: 1,
              profitability_gate_blocked: 0,
              ml_gate_passed: 1,
              ml_gate_blocked: 0,
              executable_intents: 1,
              simulated_fills: 1,
              persisted_trades: 1,
            },
            dominant_blocker: { code: 'quote_invalid', count: 1 },
          },
        }}
      />
    );

    for (const symbol of ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD', 'DOT-USD']) expect(screen.getByText(symbol)).toBeInTheDocument();
    expect(screen.getAllByText('Valid HOLD').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Executable intent').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Invalid quote').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Transformer warming').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Trade completed').length).toBeGreaterThan(0);
    expect(screen.getByText(/counts include all 5 selected symbols/)).toBeInTheDocument();
    expect(screen.getByText('Dominant blocker')).toBeInTheDocument();
    expect(screen.getByText(/quote_invalid \(1\)/)).toBeInTheDocument();
    expect(screen.getByText('Quote successes')).toBeInTheDocument();
    expect(screen.getByText('Persisted trades')).toBeInTheDocument();
  });

  it('supports symbol search, outcome grouping, and page boundaries without dropping rows', () => {
    const onPageChange = jest.fn();
    render(<OrderBookSignalsTable selectedSymbols={['A-USD', 'B-USD', 'C-USD']} signals={[signal('A-USD', { signal: 'buy', signal_generated: true }), signal('B-USD'), signal('C-USD', { signal: 'sell', signal_generated: true })]} currentPage={1} pageSize={2} onPageChange={onPageChange} />);

    expect(screen.getAllByText((_, element) => element?.textContent?.replace(/\s+/g, ' ').includes('Showing 2 of 3 matching rows') ?? false).length).toBeGreaterThan(0);
    expect(screen.getAllByText((_, element) => element?.textContent?.replace(/\s+/g, ' ').includes('Page 1 of 2') ?? false).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByRole('combobox', { name: 'Group signals by' }), { target: { value: 'quoteState' } });
    expect(screen.getByRole('table', { name: 'Order-book signals grouped by Quote state' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(onPageChange).toHaveBeenCalledWith(2);
    fireEvent.change(screen.getByRole('textbox', { name: 'Search symbols and diagnostics' }), { target: { value: 'C-USD' } });
    expect(screen.getByText('C-USD')).toBeInTheDocument();
    expect(screen.queryByText('A-USD')).not.toBeInTheDocument();
  });

  it('exposes accessible expandable details and safely renders long diagnostic strings', () => {
    const longReason = 'reason-'.repeat(100);
    render(<OrderBookSignalsTable signals={[signal('LONG-USD', { signal_reason: longReason, ml_analysis: { profitability_gate_reason: longReason, confidence: 0.82 }, execution_analysis: { blocker_reason: longReason } })]} />);
    const row = screen.getByRole('row', { name: /LONG-USD/ });
    const details = within(row).getByRole('button', { name: 'Show details for LONG-USD' });
    expect(details).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(details);
    expect(details).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText(longReason)).toBeInTheDocument();
    expect(screen.getByText(/Confidence: 82.00%/)).toBeInTheDocument();
  });

  it('distinguishes loading, empty, and error states and offers retry', () => {
    const retry = jest.fn();
    const { rerender } = render(<OrderBookSignalsTable loading />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading order-book signal coverage');
    rerender(<OrderBookSignalsTable />);
    expect(screen.getByRole('status')).toHaveTextContent('No selected symbols have been reported');
    rerender(<OrderBookSignalsTable signals={[signal('ERR-USD')]} error={new Error('server unavailable')} onRetry={retry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('server unavailable');
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
