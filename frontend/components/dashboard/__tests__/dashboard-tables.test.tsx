/** @jest-environment jsdom */

import React from 'react';
import { render, screen, within, fireEvent } from '@testing-library/react';
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
    expect(screen.getByRole('columnheader', { name: 'Opened' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Action' })).toBeInTheDocument();

    const row = screen.getByRole('row', { name: /BTC-USD/ });
    expect(within(row).getByText('BTC-USD')).toBeInTheDocument();
    expect(within(row).getByText('LONG')).toBeInTheDocument();
    expect(within(row).getByText('1.5000')).toBeInTheDocument();
    expect(within(row).getByText('$100.0000')).toBeInTheDocument();
    expect(within(row).getByText('$125.0000')).toBeInTheDocument();
    expect(within(row).getByText('$37.50')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Close' })).toBeInTheDocument();
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
            fee: 3.25,
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

    fireEvent.click(within(row).getByRole('button', { name: /Details/i }));
    expect(alertSpy).toHaveBeenCalled();
    expect(String(alertSpy.mock.calls[0][0])).toContain('Confidence: 82.00%');

    alertSpy.mockRestore();
  });
});