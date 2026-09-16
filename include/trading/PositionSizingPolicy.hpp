#pragma once

#include <cstddef>

namespace trade {
namespace trading {

struct PositionSizingInputs {
  double base_usd = 0.0;
  double signal_strength = 0.0;
  double win_probability = 0.0;
  double expected_return = 0.0;
  double model_confidence = 0.0;
  double spread_percent = 0.0;
  double volatility = 0.0;
  double live_profit_factor = 0.0;
  double live_sharpe_ratio = 0.0;
  double live_max_drawdown = 0.0;
  double live_total_fees = 0.0;
  double live_net_pnl = 0.0;
  double cohort_profit_factor = 0.0;
  double cohort_sharpe_ratio = 0.0;
  double cohort_avg_drawdown = 0.0;
  std::size_t cohort_sample_count = 0;
};

struct MinimumTradeSizeInputs {
  double price = 0.0;
  double expected_return_fraction = 0.0;
  double round_trip_fee_fraction = 0.0016;
  double slippage_buffer_fraction = 0.0;
  double spread_fraction = 0.0;
  double minimum_net_pnl_usd = 0.0;
  double configured_max_notional_usd = 0.0;
  bool allow_unprofitable_trades = false;
};

struct MinimumTradeSizeDecision {
  bool should_trade = false;
  double quantity = 0.0;
  double notional_usd = 0.0;
  double expected_net_pnl_usd = 0.0;
  double required_edge_fraction = 0.0;
};

// Textbook Kelly fraction for a binary win/loss bet: f* = p - (1-p)/b, where
// b is the win/loss payoff ratio (average win / average loss). Clamped to
// [0, 1] — a non-positive edge sizes to zero, never negative (this function
// only ever scales a long-only deployment down, not into a short position).
double kelly_fraction(double win_probability, double payoff_ratio);

double derive_position_size_multiplier(const PositionSizingInputs &inputs);
double calculate_position_size_usd(const PositionSizingInputs &inputs);
double expected_net_pnl_usd(double notional_usd, const MinimumTradeSizeInputs &inputs);
MinimumTradeSizeDecision minimum_trade_size_decision(const MinimumTradeSizeInputs &inputs);

struct ModelHealthInputs {
  double live_profit_factor = 0.0;
  int live_sample_count = 0;
  double cohort_profit_factor = 0.0;
  int cohort_sample_count = 0;
};

// A circuit breaker for a degraded ML model: once enough realized outcomes
// exist to judge it (live trades preferred; the current regime's cohort
// history only when live history is too thin), a profit factor below
// `profit_factor_floor` means the model is actively hurting expectancy, not
// merely quiet. Returns true when the caller should fall back to the
// heuristic strategy (model_version="heuristic-fallback") instead of
// continuing to gate/size on this model's output. Returns false — stay on
// the model — whenever there isn't yet enough evidence either way; a small
// sample must never be read as a verdict.
bool should_downgrade_to_heuristic(const ModelHealthInputs &inputs,
                                   double profit_factor_floor = 0.7,
                                   int min_sample_count = 20);

} // namespace trading
} // namespace trade
