import { render, screen } from '@testing-library/react';
import { SimulationOutcomeSummary } from './SimulatedTradingPanel';

describe('SimulationOutcomeSummary', () => {
  it('keeps paper-live accounting separate and renders blocker details', () => {
    render(
      <SimulationOutcomeSummary
        status={{
          mode: 'paper_live',
          summary: {
            generated: 4,
            signals_actionable: 2,
            paper_fills: 1,
            paper_blocked: 1,
            live_fills: 0,
          },
          blocked_intents: [{
            intent_id: 'intent-1',
            symbol: 'BTC-USD',
            outcome_type: 'paper_blocked',
            blockers: [{
              code: 'quote_unavailable',
              message: 'Live Coinbase quote unavailable',
              category: 'market_data',
              retryable: true,
            }],
          }],
        }}
      />
    );

    expect(screen.getByText(/paper only; no Coinbase orders are submitted/i)).toBeInTheDocument();
    expect(screen.getAllByText('1', { selector: 'strong' }).length).toBeGreaterThan(0);
    expect(screen.getByText(/quote_unavailable: Live Coinbase quote unavailable/i)).toBeInTheDocument();
    expect(screen.getByText('Live filled')).toBeInTheDocument();
  });

  it('does not render synthetic fallback content when live data is unavailable', () => {
    render(
      <SimulationOutcomeSummary
        status={{
          mode: 'paper_live',
          summary: { generated: 0, paper_fills: 0, paper_blocked: 1 },
          blocked_intents: [{
            symbol: 'ETH-USD',
            blockers: [{ code: 'quote_stale', message: 'Quote is stale' }],
          }],
        }}
      />
    );

    expect(screen.getByText(/quote_stale: Quote is stale/i)).toBeInTheDocument();
    expect(screen.queryByText(/synthetic price/i)).not.toBeInTheDocument();
  });
});
