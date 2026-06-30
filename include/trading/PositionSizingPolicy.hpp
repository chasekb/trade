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

double derive_position_size_multiplier(const PositionSizingInputs &inputs);
double calculate_position_size_usd(const PositionSizingInputs &inputs);

} // namespace trading
} // namespace trade
