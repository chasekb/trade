#include "trading/PositionSizingPolicy.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

namespace trade {
namespace trading {
namespace {

double clamp_double(double value, double low, double high) {
  return std::max(low, std::min(high, value));
}

double normalize_score(double value, double min_value, double max_value) {
  if (max_value <= min_value) {
    return 0.0;
  }
  return clamp_double((value - min_value) / (max_value - min_value), 0.0, 1.0);
}

double average_non_negative(const std::vector<double> &values) {
  double total = 0.0;
  std::size_t count = 0;
  for (double value : values) {
    if (std::isfinite(value)) {
      total += value;
      ++count;
    }
  }
  return count > 0 ? total / static_cast<double>(count) : 0.0;
}

} // namespace

double derive_position_size_multiplier(const PositionSizingInputs &inputs) {
  const double confidence_score = average_non_negative(
      {normalize_score(inputs.signal_strength, 0.0, 1.0),
       normalize_score(inputs.win_probability, 0.35, 0.75),
       normalize_score(inputs.model_confidence, 0.0, 1.0),
       normalize_score(inputs.expected_return, -0.02, 0.04)});

  double multiplier = 1.0;

  // High-confidence setups get a modest increase, while weak setups are cut.
  multiplier *= clamp_double(0.55 + confidence_score * 0.9, 0.55, 1.35);

  // Wider spreads directly reduce deployment size.
  multiplier *= clamp_double(1.0 - (std::max(0.0, inputs.spread_percent) * 40.0), 0.5, 1.0);

  // Elevated volatility lowers size, but only to a floor so the strategy still participates.
  multiplier *= clamp_double(1.0 - (std::max(0.0, inputs.volatility) * 0.1), 0.7, 1.05);

  const double live_performance =
      clamp_double(1.0 + (inputs.live_profit_factor - 1.0) * 0.35 +
                       inputs.live_sharpe_ratio * 0.05 -
                       inputs.live_max_drawdown / std::max(1000.0, inputs.base_usd * 12.0) -
                       inputs.live_total_fees / std::max(1000.0, inputs.base_usd * 6.0),
                   0.65, 1.25);
  multiplier *= live_performance;

  if (inputs.cohort_sample_count > 0) {
    const double cohort_multiplier =
        clamp_double(1.0 + (inputs.cohort_profit_factor - 1.0) * 0.25 +
                         inputs.cohort_sharpe_ratio * 0.04 -
                         inputs.cohort_avg_drawdown / std::max(1000.0, inputs.base_usd * 10.0),
                     0.75, 1.2);
    multiplier *= cohort_multiplier;
  }

  if (inputs.live_net_pnl < 0.0) {
    multiplier *= 0.9;
  }

  return clamp_double(multiplier, 0.35, 1.5);
}

double calculate_position_size_usd(const PositionSizingInputs &inputs) {
  const double base_usd = std::max(25.0, inputs.base_usd);
  return std::max(25.0, base_usd * derive_position_size_multiplier(inputs));
}

} // namespace trading
} // namespace trade
