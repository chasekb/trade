/** @jest-environment jsdom */

import React from 'react';
import { render, screen, within } from '@testing-library/react';
import ExecutionReconciliationTable from '../ExecutionReconciliationTable';
import { normalizeExecutionReconciliation } from '@/lib/executionReconciliation';

const representativePayload = {
  window_hours: 6,
  trade_type: 'live_parity',
  signal_rows: 12,
  outcome_rows: 3,
  signal_rows_truncated: true,
  session_id: 'must-not-render-this-session-id',
  error: 'database credentials must not render',
  by_strategy: [
    {
      strategy: 'orderbook',
      signals_evaluated: 10,
      signals_generated: 6,
      executable_intents: 2,
      blocked_intents: 4,
      closing_legs: 2,
      winners: 1,
      losers: 1,
      win_rate: 50,
      average_win: 12.5,
      average_loss: 4.25,
      expectancy: 4.12,
      total_pnl: 8.25,
      total_fees: 0.5,
      intent_conversion_rate: 0.333,
      outcome_coverage: 0.75,
      outcomes_unexplained: true,
      blockers: [
        { reason: 'insufficient_history', count: 2, share: 0.5 },
        { reason: 'spot_cannot_open_short', count: 2, share: 0.5 },
      ],
    },
    {
      strategy: 'rsi',
      signals_evaluated: 2,
      signals_generated: 1,
      executable_intents: 0,
      blocked_intents: 1,
      blockers: [{ reason: 'live_execution_disabled', count: 1, share: 1 }],
    },
  ],
  overall: {
    strategy: 'overall',
    signals_evaluated: 12,
    signals_generated: 7,
    executable_intents: 2,
    blocked_intents: 5,
    closing_legs: 2,
    outcome_coverage: 0.75,
    outcomes_unexplained: true,
    expectancy: 4.12,
  },
};

function renderPayload(payload: unknown = representativePayload) {
  return render(
    <ExecutionReconciliationTable
      reconciliation={normalizeExecutionReconciliation(payload)}
      modeLabel="Live parity (no order submission)"
    />,
  );
}

describe('ExecutionReconciliationTable', () => {
  it('renders loading, API-error, and empty states safely', () => {
    const { rerender } = render(<ExecutionReconciliationTable reconciliation={null} isLoading />);
    expect(screen.getByText('Loading execution reconciliation…')).toBeInTheDocument();

    rerender(<ExecutionReconciliationTable reconciliation={null} error={new Error('private backend detail')} />);
    expect(screen.getByText('Execution reconciliation unavailable. Try refreshing this panel.')).toBeInTheDocument();
    expect(screen.queryByText('private backend detail')).not.toBeInTheDocument();

    rerender(<ExecutionReconciliationTable reconciliation={normalizeExecutionReconciliation({})} />);
    expect(screen.getByText('No signals or outcomes recorded in this window.')).toBeInTheDocument();
  });

  it('renders representative outcomes, reconciliation gaps, and objective metrics', () => {
    renderPayload();

    expect(screen.getByText(/Live parity \(no order submission\)/)).toBeInTheDocument();
    expect(screen.getByText('Generated signals')).toBeInTheDocument();
    expect(screen.getByText('Hold / skip unresolved')).toBeInTheDocument();
    expect(screen.getByText('Eligible intents (not fills)')).toBeInTheDocument();
    expect(screen.getByText('Realized closing outcomes')).toBeInTheDocument();
    expect(screen.getAllByText('$4.12')).toHaveLength(2);
    expect(screen.getByText(/Signal rows were truncated/)).toBeInTheDocument();
    expect(screen.getByText(/Runtime reconciliation coverage: 75.0%/)).toBeInTheDocument();
    expect(screen.getByText(/Some outcomes are not explained/)).toBeInTheDocument();

    const orderbook = screen.getByRole('row', { name: /orderbook/ });
    expect(within(orderbook).getByText('6')).toBeInTheDocument();
    expect(within(orderbook).getAllByText('2')).toHaveLength(2);
    expect(within(orderbook).getByText('$12.50')).toBeInTheDocument();
    expect(within(orderbook).getByText('$4.25')).toBeInTheDocument();
  });

  it('keeps signal-quality and execution-policy blockers visibly distinct', () => {
    renderPayload();

    const quality = screen.getByRole('heading', { name: 'Signal-quality blockers' }).parentElement;
    const policy = screen.getByRole('heading', { name: 'Execution policy / account / exchange blockers' }).parentElement;
    expect(quality).not.toBeNull();
    expect(policy).not.toBeNull();
    expect(within(quality as HTMLElement).getByText('insufficient_history')).toBeInTheDocument();
    expect(within(policy as HTMLElement).getByText('spot_cannot_open_short')).toBeInTheDocument();
    expect(within(policy as HTMLElement).getByText('live_execution_disabled')).toBeInTheDocument();
    expect(within(quality as HTMLElement).queryByText('spot_cannot_open_short')).not.toBeInTheDocument();
  });

  it('states unavailable dimensions and never exposes secrets or account details', () => {
    renderPayload();

    expect(screen.getByText(/Unavailable from reconciliation endpoint:/)).toBeInTheDocument();
    expect(screen.getByText(/Symbol, Side, Diagnostic factor, Strength bucket, Expected-return bucket/)).toBeInTheDocument();
    expect(screen.queryByText('must-not-render-this-session-id')).not.toBeInTheDocument();
    expect(screen.queryByText('database credentials must not render')).not.toBeInTheDocument();
    expect(screen.queryByText(/account balance|api key|secret/i)).not.toBeInTheDocument();
  });

  it('renders partial rows with missing optional fields without inventing execution', () => {
    renderPayload({
      trade_type: 'simulated',
      by_strategy: [{ strategy: 'sma', signals_generated: 1, executable_intents: 1 }],
    });

    expect(screen.getByText('sma')).toBeInTheDocument();
    expect(screen.getByText('Eligible intents (not fills)')).toBeInTheDocument();
    expect(screen.queryByText(/executed/i)).not.toBeInTheDocument();
  });
});
