#pragma once

#include <cstddef>
#include <string>
#include <vector>

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

// A single regime's recorded cohort performance, as consumed by cohort-aware
// sizing below. Mirrors the subset of ml::ExecutionCohortMetrics actually
// used here; kept independent of that type so this module has no dependency
// on the ml/ExecutionCohorts module (callers map their own cohort records
// into this struct).
struct RegimeCohortSample {
  std::string regime;
  double profit_factor = 0.0;
  double sharpe_ratio = 0.0;
  double max_drawdown = 0.0;
  int sample_count = 0;
};

struct CohortSizingSelection {
  double profit_factor = 0.0;
  double sharpe_ratio = 0.0;
  double avg_drawdown = 0.0;
  std::size_t sample_count = 0;
};

// Resolves which recorded cohort performance should inform sizing for a
// signal in the given regime: that regime's own history once it has at
// least `min_regime_sample_count` samples to trust (a signal in a thin,
// volatile session should be sized off how that regime actually performed,
// not diluted by unrelated conditions), otherwise a sample-weighted average
// across every recorded regime. Falls back to the blended average — never
// to zero — when `execution_regime` is empty (no regime tagging on this
// signal) or no matching regime has enough history yet; returns a
// zero-valued, zero-sample selection when there is no cohort data at all.
CohortSizingSelection resolve_cohort_sizing_inputs(
    const std::string &execution_regime, const std::vector<RegimeCohortSample> &cohort_samples,
    int min_regime_sample_count = 5);

} // namespace trading
} // namespace trade
