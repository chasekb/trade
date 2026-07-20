#include "trading/PositionSizingPolicy.hpp"

#include <cmath>
#include <iostream>

int main() {
  trade::trading::PositionSizingInputs weak{};
  weak.base_usd = 1000.0;
  weak.signal_strength = 0.1;
  weak.win_probability = 0.4;
  weak.expected_return = -0.01;
  weak.model_confidence = 0.1;
  weak.spread_percent = 0.01;
  weak.volatility = 2.0;
  weak.live_profit_factor = 0.8;
  weak.live_sharpe_ratio = -0.5;
  weak.live_max_drawdown = 200.0;
  weak.live_total_fees = 80.0;
  weak.live_net_pnl = -100.0;
  weak.cohort_profit_factor = 0.8;
  weak.cohort_sharpe_ratio = -0.2;
  weak.cohort_avg_drawdown = 100.0;
  weak.cohort_sample_count = 20;

  trade::trading::PositionSizingInputs strong{};
  strong.base_usd = 1000.0;
  strong.signal_strength = 0.9;
  strong.win_probability = 0.7;
  strong.expected_return = 0.03;
  strong.model_confidence = 0.95;
  strong.spread_percent = 0.0002;
  strong.volatility = 0.1;
  strong.live_profit_factor = 1.4;
  strong.live_sharpe_ratio = 1.2;
  strong.live_max_drawdown = 20.0;
  strong.live_total_fees = 5.0;
  strong.live_net_pnl = 200.0;
  strong.cohort_profit_factor = 1.3;
  strong.cohort_sharpe_ratio = 0.8;
  strong.cohort_avg_drawdown = 10.0;
  strong.cohort_sample_count = 50;

  const double weak_multiplier = trade::trading::derive_position_size_multiplier(weak);
  const double strong_multiplier = trade::trading::derive_position_size_multiplier(strong);
  const double weak_size = trade::trading::calculate_position_size_usd(weak);
  const double strong_size = trade::trading::calculate_position_size_usd(strong);

  if (!(weak_multiplier < 1.0)) {
    std::cerr << "Weak setup should reduce position size" << std::endl;
    return 1;
  }
  if (!(strong_multiplier > 1.0)) {
    std::cerr << "Strong setup should increase position size" << std::endl;
    return 1;
  }
  if (!(strong_size > weak_size)) {
    std::cerr << "Strong size should exceed weak size" << std::endl;
    return 1;
  }
  if (strong_size > strong.base_usd) {
    std::cerr << "Configured position size must remain a hard maximum" << std::endl;
    return 1;
  }
  if (!(weak_size < 1000.0)) {
    std::cerr << "Weak setup should stay below base size" << std::endl;
    return 1;
  }

  trade::trading::PositionSizingInputs small{};
  small.base_usd = 1.0;
  small.signal_strength = 0.5;
  small.win_probability = 0.5;
  small.model_confidence = 0.5;
  small.live_profit_factor = 1.0;
  const double expected_small_size =
      small.base_usd * trade::trading::derive_position_size_multiplier(small);
  const double actual_small_size = trade::trading::calculate_position_size_usd(small);
  if (std::fabs(actual_small_size - expected_small_size) > 1e-9) {
    std::cerr << "Small calculated size should not be raised to an exchange minimum: expected "
              << expected_small_size << " got " << actual_small_size << std::endl;
    return 1;
  }

  trade::trading::PositionSizingInputs zero{};
  if (trade::trading::calculate_position_size_usd(zero) != 0.0) {
    std::cerr << "Zero configured size should remain zero" << std::endl;
    return 1;
  }
  return 0;
}
