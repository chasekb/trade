#pragma once

#include "trading/StrategySignal.hpp"

#include <deque>
#include <map>
#include <string>
#include <vector>

namespace trade {
namespace trading {

struct StrategyExpectancyFixture {
  std::string name;
  std::string strategy;
  std::deque<double> prices;
  StrategyParams params;
  bool has_position = false;
  long long ticks_since_last_entry = 0;

  // Optional direct signal for order-book fixtures, whose signal producer is
  // intentionally outside evaluateStrategySignal().
  std::string signal_type;
  double signal_strength = 1.0;
  bool expected_return_available = false;
  double expected_return_fraction = 0.0;
  double spread_fraction = 0.0;
  double round_trip_fee_fraction = 0.015;
  double slippage_buffer_fraction = 0.002;
  double min_signal_strength = 0.2;

  // Net realized outcome after fees/spread/slippage for the paper/backtest fill.
  // Positive values are wins, negative values are losses, and zero values are
  // excluded from average-win/loss denominators.
  double realized_pnl = 0.0;
  bool blocked = false;
  std::string blocked_reason;
};

struct StrategyExpectancyRow {
  std::string fixture_name;
  std::string strategy;
  std::string signal_type = "hold";
  double signal_strength = 0.0;
  bool diagnostics_available = false;
  bool profitability_actionable = false;
  std::string diagnostic_factor;
  double directional_expected_edge_fraction = 0.0;
  double fee_adjusted_expected_return_fraction = 0.0;
  double required_edge_fraction = 0.0;
  bool filled = false;
  bool blocked = false;
  std::string blocked_reason;
  std::string factoring_semantics;
  double realized_pnl = 0.0;
};

struct StrategyExpectancyMetrics {
  std::size_t fixtures = 0;
  std::size_t signals_generated = 0;
  std::size_t trades_filled = 0;
  std::size_t blocked_intents = 0;
  double average_win = 0.0;
  double average_loss = 0.0;
  double expectancy = 0.0;
  double profit_factor = 0.0;
  double max_drawdown = 0.0;
  double total_pnl = 0.0;
  bool negative_expectancy_flag = false;
};

struct StrategyExpectancyReport {
  std::vector<StrategyExpectancyRow> rows;
  std::map<std::string, StrategyExpectancyMetrics> by_strategy;
  StrategyExpectancyMetrics overall;
};

StrategyExpectancyReport evaluateStrategyExpectancy(
    const std::vector<StrategyExpectancyFixture> &fixtures);

std::vector<StrategyExpectancyFixture> defaultStrategyExpectancyFixtures();

} // namespace trading
} // namespace trade
