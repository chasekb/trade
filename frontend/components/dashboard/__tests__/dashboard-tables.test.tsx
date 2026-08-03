/** @jest-environment jsdom */

import React from 'react';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import { OpenPositionsSection } from '../OpenPositionsSection';
import { RecentTradesTable } from '../RecentTradesTable';
import { OrderBookSignalsTable } from '../OrderBookSignalsTable';

describe('trade dashboard tables', () => {
  it('renders open positions values and columns', () => {
    render(
      <OpenPositionsSection
        positions={[
          {
            symbol: 'BTC-USD',
            side: 'long',
            quantity: 1.5,
            entry_price: 100,
            current_price: 125,
            unrealized_pnl: 37.5,
            entry_time: '2026-07-06T12:00:00Z',
          },
        ]}
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
    render(
      <OpenPositionsSection
        positions={[
          {
            symbol: 'ETH-USD',
            side: 'buy',
            quantity: 0.25,
            entry_price: 3500,
            current_price: 3510,
            unrealized_pnl: 0,
            entry_time: '2026-07-06T12:00:00Z',
            session_managed: true,
            inherited_quantity: 0.25,
            management_state: 'account_managed',
          },
        ]}
        onClose={jest.fn()}
      />
    );

    const row = screen.getByRole('row', { name: /ETH-USD/ });
    expect(within(row).getByText('Account-managed')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });

  it('renders explicit liquidation controls for Coinbase-only holdings', async () => {
    const liquidateHolding = jest.fn();
    const liquidateAll = jest.fn();

    render(
      <OpenPositionsSection
        positions={[
          {
            symbol: 'ADA-USD',
            side: 'long',
            quantity: 25,
            entry_price: 0.5,
            current_price: 0.51,
            unrealized_pnl: 0,
            entry_time: '2026-07-06T12:00:00Z',
            session_managed: false,
          },
        ]}
        onClose={jest.fn()}
        onLiquidateHolding={liquidateHolding}
        onLiquidateAllHoldings={liquidateAll}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Liquidate holding' }));
    await waitFor(() => expect(liquidateHolding).toHaveBeenCalledWith('ADA-USD'));

    fireEvent.click(screen.getByRole('button', { name: /Liquidate all Coinbase holdings/ }));
    await waitFor(() => expect(liquidateAll).toHaveBeenCalled());
  });

  it('renders recent trades values and optional fees column', () => {
    render(
      <RecentTradesTable
        includeFees
        trades={[
          {
            timestamp: '2026-07-06T12:30:00Z',
            symbol: 'ETH-USD',
            side: 'buy',
            quantity: 2,
            price: 2500,
            fees: 3.25,
            pnl: 125.5,
          },
        ]}
      />
    );

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

  it('renders order book signal values and ML analysis formatting', () => {
    const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});

    render(
      <OrderBookSignalsTable
        signals={[
          {
            symbol: 'SOL-USD',
            timestamp: '2026-07-06T12:45:00Z',
            price: 160.12,
            signal: 'sell',
            signal_generated: true,
            signal_strength: 0.88,
            signal_type: 'sell',
            signal_reason: 'Strong sell pressure',
            data_status: 'sufficient',
            spread: 0.1234,
            volume: 1234.56,
            criteria_analysis: {
              bid_ask_squeeze: { enabled: true, meets_criteria: true, delta_to_threshold: 0.02, threshold_spread: 0.05, analysis: 'ok' },
              volume_imbalance_buy: { enabled: true, meets_criteria: false, delta_to_threshold: -0.01, threshold: 0.4, analysis: 'not met' },
              large_trade_buy: { enabled: false, meets_criteria: false, delta_to_threshold: 0, large_trades_count: 0, analysis: 'disabled' },
            },
            ml_analysis: {
              ml_enabled: true,
              win_probability: 0.67,
              expected_return: 0.045,
              fee_adjusted_expected_return: 0.028,
              required_edge: 0.017,
              profitability_gate_reason: 'Expected edge exceeds fee/spread/slippage hurdle',
              confidence: 0.82,
              model_version: 'v1.2.3',
              prediction_timestamp: '2026-07-06T12:44:59Z',
              analytics: { roc_auc: 0.91 },
            },
            strength_composition: {
              momentum: { value: 0.7, importance_percent: 60 },
            },
          },
        ]}
        currentPage={1}
        pageSize={10}
        summary={{ total_analyzed: 1, active_signals: 1, average_strength: 0.88, last_updated: '2026-07-06T12:46:00Z' }}
      />
    );

    expect(screen.getByRole('columnheader', { name: 'Symbol' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Price' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Signal' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Strength' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Spread' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Volume' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Criteria' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'ML Analysis' })).toBeInTheDocument();

    const row = screen.getByRole('row', { name: /SOL-USD/ });
    expect(within(row).getByText('SOL-USD')).toBeInTheDocument();
    expect(within(row).getByText('$160.12')).toBeInTheDocument();
    expect(within(row).getByText('SELL')).toBeInTheDocument();
    expect(within(row).getByText('0.88')).toBeInTheDocument();
    expect(within(row).getByText('0.1234%')).toBeInTheDocument();
    expect(within(row).getByText('1234.56')).toBeInTheDocument();
    expect(within(row).getByText('Win Probability: 67.00%')).toBeInTheDocument();
    expect(within(row).getByText('Expected Return: 4.50%')).toBeInTheDocument();
    expect(within(row).getByText('Fee-Adjusted Edge: 2.80%')).toBeInTheDocument();
    expect(within(row).getByText('Required Edge: 1.70%')).toBeInTheDocument();

    fireEvent.click(within(row).getByRole('button', { name: /Details/i }));
    expect(alertSpy).toHaveBeenCalled();
    expect(String(alertSpy.mock.calls[0][0])).toContain('Confidence: 82.00%');
    expect(String(alertSpy.mock.calls[0][0])).toContain('Profitability Gate: Expected edge exceeds fee/spread/slippage hurdle');

    alertSpy.mockRestore();
  });

  it('renders profitability-gated holds as sufficient data instead of waiting', () => {
    render(
      <OrderBookSignalsTable
        signals={[
          {
            symbol: 'BTC-USD',
            timestamp: '2026-07-06T12:50:00Z',
            price: 64500,
            signal: 'hold',
            signal_generated: false,
            signal_strength: 0,
            signal_type: 'hold',
            signal_reason: 'Expected edge 0.006 below fee/spread/slippage hurdle 0.017',
            data_status: 'sufficient',
            spread: 0.04,
            volume: 5000,
            criteria_analysis: {},
            ml_analysis: {
              ml_enabled: true,
              win_probability: 0.58,
              expected_return: 0.006,
              fee_adjusted_expected_return: -0.011,
              required_edge: 0.017,
              profitability_gate_passed: false,
              profitability_gate_reason: 'Expected edge 0.006 below fee/spread/slippage hurdle 0.017',
              confidence: 0.44,
              model_version: 'heuristic-fallback',
              prediction_timestamp: '2026-07-06T12:49:59Z',
            },
            strength_composition: {},
          },
        ]}
        currentPage={1}
        pageSize={10}
      />
    );

    const row = screen.getByRole('row', { name: /BTC-USD/ });
    expect(within(row).getByText('HOLD')).toBeInTheDocument();
    expect(within(row).queryByText('WAITING')).not.toBeInTheDocument();
    expect(within(row).getByText('Fee-Adjusted Edge: -1.10%')).toBeInTheDocument();
    expect(within(row).getByText('Required Edge: 1.70%')).toBeInTheDocument();
  });

  it('renders live order-book coverage diagnostics when a per-tick quote cap applies', () => {
    render(
      <OrderBookSignalsTable
        signals={[]}
        currentPage={1}
        pageSize={10}
        summary={{
          diagnostics: {
            selected_symbol_count: 32,
            requested_symbol_count: 32,
            quote_attempted_symbol_count: 10,
            quote_success_symbol_count: 9,
            quote_skipped_symbol_count: 22,
            live_quote_symbols_per_tick_cap: 10,
            current_latest_signal_count: 10,
            missing_latest_signal_count: 22,
            missing_latest_signal_symbols: ['ADA-USD', 'DOT-USD'],
            recent_signal_record_count: 10,
            widget_coverage_contract: 'Signals include response-only missing rows for selected symbols without a latest live quote so widget pagination represents the full selected universe.',
            contract: 'Live order-book quotes are capped per tick for Coinbase cadence safety and rotated across the selected universe.',
          },
        }}
      />
    );

    expect(screen.getByText('Live order-book analysis coverage')).toBeInTheDocument();
    expect(screen.getByText('Selected: 32')).toBeInTheDocument();
    expect(screen.getByText('Attempted this tick: 10')).toBeInTheDocument();
    expect(screen.getByText('Quote successes: 9')).toBeInTheDocument();
    expect(screen.getByText('Missing latest rows: 22')).toBeInTheDocument();
    expect(screen.getByText('Awaiting latest quote/signal: ADA-USD, DOT-USD')).toBeInTheDocument();
    expect(screen.getByText(/Per-tick cap: 10 symbols/)).toBeInTheDocument();
    expect(screen.getByText(/pagination represents the full selected universe/)).toBeInTheDocument();
    expect(screen.getByText(/rotated across the selected universe/)).toBeInTheDocument();
  });
});
