/** @jest-environment jsdom */

import React from 'react';
import { render, screen } from '@testing-library/react';
import ExecutionAttributionSummary from './ExecutionAttributionSummary';
import { normalizeExecutionAttribution } from '@/lib/executionAttribution';
import fixture from '../../../tests/fixtures/execution_attribution_report.json';

describe('ExecutionAttributionSummary', () => {
  it('renders a loading state without touching the report', () => {
    render(<ExecutionAttributionSummary report={null} isLoading title="Live execution attribution" />);
    expect(screen.getByText('Loading execution attribution…')).toBeInTheDocument();
  });

  it('renders an error state instead of a blank widget', () => {
    render(
      <ExecutionAttributionSummary
        report={null}
        error={new Error('boom')}
        title="Live execution attribution"
      />,
    );
    expect(screen.getByText(/Execution attribution unavailable/)).toBeInTheDocument();
  });

  it('shows an empty-state message when there is no attribution data', () => {
    render(
      <ExecutionAttributionSummary
        report={normalizeExecutionAttribution(null)}
        title="Live execution attribution"
      />,
    );
    expect(
      screen.getByText('No attribution data is available for this runtime window.'),
    ).toBeInTheDocument();
  });

  it('renders strategy rows, blocker/diagnostic counts, and dimension tables without coercing missing win rates to zero', () => {
    const report = normalizeExecutionAttribution(fixture);
    render(<ExecutionAttributionSummary report={report} title="Live execution attribution" />);

    expect(screen.getByText('orderbook')).toBeInTheDocument();
    expect(screen.getByText('pending_order')).toBeInTheDocument();
    // Appears both in the strategy's diagnostic-factor counts and in the
    // bottom-level "Diagnostic-factor impact" table.
    expect(screen.getAllByText('account_or_exchange_blocker').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('BTC-USD')).toBeInTheDocument();
    // BTC-USD's real win rate (100.0%) and ETH-USD's real, legitimate zero
    // win rate (0.0%) both render as actual numbers.
    expect(screen.getByText('100.0%')).toBeInTheDocument();
    expect(screen.getByText('0.0%')).toBeInTheDocument();

    // The strength-bucket dimension has no outcome linkage; its win rate
    // must render as the null placeholder, never as a fabricated 0.0%.
    const strengthRow = screen.getByText('strong').closest('tr');
    expect(strengthRow).not.toBeNull();
    expect(strengthRow).toHaveTextContent('—');

    expect(screen.getByText('Diagnostic-factor impact')).toBeInTheDocument();
    expect(screen.getAllByText('weak_strength').length).toBeGreaterThanOrEqual(1);
  });
});
