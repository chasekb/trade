/** @jest-environment jsdom */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { StrategySelector } from './StrategySelector';

const evaluatedStrategies = [
  'Simple Moving Average',
  'Exponential Moving Average',
  'RSI Strategy',
  'Bollinger Bands',
  'MACD Strategy',
  'Stochastic Oscillator',
  'Fibonacci Retracement',
  'Dollar Cost Average',
  'Buy and Hold',
  'Order Book Signals',
];

describe('StrategySelector calibration status', () => {
  it('labels every evaluated strategy as deferred instead of implying promotion', () => {
    render(<StrategySelector value="ml_enhanced_orderbook" onChange={jest.fn()} />);

    const options = screen.getAllByRole('option');
    for (const strategy of evaluatedStrategies) {
      const option = options.find((candidate) => candidate.textContent?.startsWith(strategy));
      expect(option).toBeDefined();
      expect(option).toHaveTextContent('calibration deferred');
    }
  });

  it('keeps the existing ML order-book selection as an explicitly uncalibrated baseline', () => {
    render(<StrategySelector value="ml_enhanced_orderbook" onChange={jest.fn()} />);

    expect(screen.getByRole('option', { name: /ML-Enhanced Order Book/ })).toHaveTextContent('baseline');
    expect(screen.getByText(/Calibration is deferred for every evaluated strategy/)).toBeInTheDocument();
  });
});
