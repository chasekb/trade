#include "trading/PositionSizingPolicy.hpp"

#include <cmath>
#include <iostream>

int main() {
  // kelly_fraction: a sub-50% edge sizes to zero (never negative — this
  // scales a long-only deployment down, not into a short); a genuine edge
  // scales up toward, but never past, full Kelly.
  if (trade::trading::kelly_fraction(0.5, 1.0) != 0.0) {
    std::cerr << "A coin-flip edge should carry zero Kelly fraction at even-money payoff"
              << std::endl;
    return 1;
  }
  if (trade::trading::kelly_fraction(0.3, 1.0) != 0.0) {
    std::cerr << "A sub-50% edge must clamp to zero, not go negative" << std::endl;
    return 1;
  }
  if (std::fabs(trade::trading::kelly_fraction(0.7, 1.0) - 0.4) > 1e-9) {
    std::cerr << "Kelly fraction at p=0.7, b=1 should be exactly 2p-1=0.4" << std::endl;
    return 1;
  }
  if (trade::trading::kelly_fraction(1.0, 1.0) != 1.0) {
    std::cerr << "A certain win should saturate Kelly fraction at 1.0" << std::endl;
    return 1;
  }

  // A higher calibrated win_probability must size strictly larger than a
  // weaker one when every other input is identical. The Kelly term above
  // reinforces this alongside the pre-existing confidence blend.
  {
    trade::trading::PositionSizingInputs base{};
    base.base_usd = 1000.0;
    base.signal_strength = 0.5;
    base.model_confidence = 0.5;
    base.expected_return = 0.01;
    base.live_profit_factor = 1.0;

    trade::trading::PositionSizingInputs low_prob = base;
    low_prob.win_probability = 0.42;
    trade::trading::PositionSizingInputs high_prob = base;
    high_prob.win_probability = 0.72;

    const double low_multiplier = trade::trading::derive_position_size_multiplier(low_prob);
    const double high_multiplier = trade::trading::derive_position_size_multiplier(high_prob);
    if (!(high_multiplier > low_multiplier)) {
      std::cerr << "A higher calibrated win probability should size strictly larger, all else equal"
                << std::endl;
      return 1;
    }
  }

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

  trade::trading::MinimumTradeSizeInputs profitable{};
  profitable.price = 100.0;
  profitable.expected_return_fraction = 0.03;
  profitable.round_trip_fee_fraction = 0.0016;
  profitable.slippage_buffer_fraction = 0.002;
  profitable.spread_fraction = 0.001;
  profitable.minimum_net_pnl_usd = 1.0;
  profitable.configured_max_notional_usd = 100.0;
  const auto profitable_decision = trade::trading::minimum_trade_size_decision(profitable);
  if (!profitable_decision.should_trade || profitable_decision.notional_usd > 100.0) {
    std::cerr << "Profitable expected-return setup should trade within cap" << std::endl;
    return 1;
  }

  trade::trading::MinimumTradeSizeInputs fee_blocked = profitable;
  fee_blocked.expected_return_fraction = 0.002;
  const auto fee_blocked_decision = trade::trading::minimum_trade_size_decision(fee_blocked);
  if (fee_blocked_decision.should_trade) {
    std::cerr << "Fee/slippage/spread hurdle should block insufficient edge" << std::endl;
    return 1;
  }

  trade::trading::MinimumTradeSizeInputs cap_blocked = profitable;
  cap_blocked.minimum_net_pnl_usd = 10.0;
  cap_blocked.configured_max_notional_usd = 50.0;
  const auto cap_blocked_decision = trade::trading::minimum_trade_size_decision(cap_blocked);
  if (cap_blocked_decision.should_trade) {
    std::cerr << "Position cap should block trades below minimum profitable notional" << std::endl;
    return 1;
  }

  trade::trading::MinimumTradeSizeInputs override = fee_blocked;
  override.allow_unprofitable_trades = true;
  const auto override_decision = trade::trading::minimum_trade_size_decision(override);
  if (!override_decision.should_trade) {
    std::cerr << "Explicit override should allow unprofitable trades" << std::endl;
    return 1;
  }

  // Circuit breaker: enough samples and a degraded profit factor downgrades.
  {
    trade::trading::ModelHealthInputs degraded_live{};
    degraded_live.live_profit_factor = 0.5;
    degraded_live.live_sample_count = 30;
    if (!trade::trading::should_downgrade_to_heuristic(degraded_live)) {
      std::cerr << "A degraded live profit factor with enough samples should downgrade"
                << std::endl;
      return 1;
    }
  }

  // A thin sample must never be read as a verdict, even if it looks bad.
  {
    trade::trading::ModelHealthInputs thin_sample{};
    thin_sample.live_profit_factor = 0.1;
    thin_sample.live_sample_count = 3;
    thin_sample.cohort_profit_factor = 0.1;
    thin_sample.cohort_sample_count = 2;
    if (trade::trading::should_downgrade_to_heuristic(thin_sample)) {
      std::cerr << "A thin sample should not trigger the circuit breaker" << std::endl;
      return 1;
    }
  }

  // Healthy live performance never downgrades even if the cohort looks weak.
  {
    trade::trading::ModelHealthInputs healthy_live{};
    healthy_live.live_profit_factor = 1.4;
    healthy_live.live_sample_count = 25;
    healthy_live.cohort_profit_factor = 0.2;
    healthy_live.cohort_sample_count = 100;
    if (trade::trading::should_downgrade_to_heuristic(healthy_live)) {
      std::cerr << "Sufficient healthy live samples should take priority over cohort history"
                << std::endl;
      return 1;
    }
  }

  // With too few live samples, fall back to cohort evidence.
  {
    trade::trading::ModelHealthInputs cohort_only{};
    cohort_only.live_profit_factor = 1.4;
    cohort_only.live_sample_count = 2;
    cohort_only.cohort_profit_factor = 0.3;
    cohort_only.cohort_sample_count = 40;
    if (!trade::trading::should_downgrade_to_heuristic(cohort_only)) {
      std::cerr << "Degraded cohort performance should downgrade when live history is too thin"
                << std::endl;
      return 1;
    }
  }

  return 0;
}
