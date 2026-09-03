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
  const double base_usd = std::max(0.0, inputs.base_usd);
  // The configured dollar amount or percentage-derived allocation is a hard
  // risk ceiling. Signal and performance inputs may reduce deployment, but
  // must never leverage the user's maximum upward.
  return base_usd * std::min(1.0, derive_position_size_multiplier(inputs));
}

double expected_net_pnl_usd(double notional_usd, const MinimumTradeSizeInputs &inputs) {
  const double notional = std::max(0.0, notional_usd);
  const double required_edge = std::max(0.0, inputs.round_trip_fee_fraction) +
                               std::max(0.0, inputs.slippage_buffer_fraction) +
                               std::max(0.0, inputs.spread_fraction);
  return notional * (inputs.expected_return_fraction - required_edge);
}

MinimumTradeSizeDecision minimum_trade_size_decision(const MinimumTradeSizeInputs &inputs) {
  MinimumTradeSizeDecision decision;
  decision.required_edge_fraction = std::max(0.0, inputs.round_trip_fee_fraction) +
                                    std::max(0.0, inputs.slippage_buffer_fraction) +
                                    std::max(0.0, inputs.spread_fraction);

  const double cap = std::max(0.0, inputs.configured_max_notional_usd);
  const double price = std::max(0.0, inputs.price);
  if (cap <= 0.0 || price <= 0.0) {
    return decision;
  }

  const double edge = inputs.expected_return_fraction - decision.required_edge_fraction;
  if (inputs.allow_unprofitable_trades) {
    decision.notional_usd = cap;
    decision.quantity = cap / price;
    decision.expected_net_pnl_usd = expected_net_pnl_usd(cap, inputs);
    decision.should_trade = true;
    return decision;
  }
  if (edge <= 0.0) {
    decision.expected_net_pnl_usd = expected_net_pnl_usd(cap, inputs);
    return decision;
  }

  const double minimum_notional = std::max(0.0, inputs.minimum_net_pnl_usd) / edge;
  const double desired_notional = std::max(minimum_notional, 0.0);
  if (desired_notional > cap) {
    decision.notional_usd = cap;
    decision.expected_net_pnl_usd = expected_net_pnl_usd(cap, inputs);
    decision.should_trade = decision.expected_net_pnl_usd >= std::max(0.0, inputs.minimum_net_pnl_usd);
    decision.quantity = decision.should_trade ? cap / price : 0.0;
    return decision;
  }

  decision.notional_usd = desired_notional > 0.0 ? desired_notional : cap;
  decision.quantity = decision.notional_usd / price;
  decision.expected_net_pnl_usd = expected_net_pnl_usd(decision.notional_usd, inputs);
  decision.should_trade = decision.expected_net_pnl_usd >= std::max(0.0, inputs.minimum_net_pnl_usd);
  return decision;
}

} // namespace trading
} // namespace trade
