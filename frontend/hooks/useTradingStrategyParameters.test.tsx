/** @jest-environment jsdom */

import { renderHook } from '@testing-library/react';
import { useStrategyParameters } from './useTrading';

describe('useStrategyParameters', () => {
  it('exposes order-book risk controls for ml_enhanced_orderbook', () => {
    const { result } = renderHook(() => useStrategyParameters());
    const names = result.current.getStrategyParameters('ml_enhanced_orderbook').map((param) => param.name);

    expect(names).toEqual(expect.arrayContaining([
      'max_positions_per_session',
      'round_trip_fee_percent',
      'slippage_buffer_percent',
      'bid_ask_spread_threshold',
      'min_orderbook_signal_strength',
      'minimum_net_pnl_usd',
    ]));
  });

  it('provides presets with explicit max-position and profitability settings', () => {
    const { result } = renderHook(() => useStrategyParameters());
    const presets = result.current.getOrderBookPresets();

    expect(presets.conservative.max_positions_per_session).toBe(25);
    expect(presets.moderate.min_orderbook_signal_strength).toBe(0.4);
    expect(presets.aggressive.minimum_net_pnl_usd).toBe(0);
    expect(presets['very-aggressive'].max_positions_per_session).toBe(250);
  });
});
