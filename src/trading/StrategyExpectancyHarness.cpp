#include "trading/StrategyExpectancyHarness.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <utility>

namespace trade {
namespace trading {
namespace {

std::deque<double> linearSeries(double start, double step, std::size_t count) {
  std::deque<double> prices;
  for (std::size_t i = 0; i < count; ++i) {
    prices.push_back(start + step * static_cast<double>(i));
  }
  return prices;
}

std::deque<double> bollingerExtreme(double final_price) {
  auto prices = linearSeries(100.0, 0.0, 25);
  prices.back() = final_price;
  return prices;
}

std::deque<double> fibonacciPullback() {
  std::deque<double> prices;
  for (int i = 0; i <= 10; ++i) {
    prices.push_back(100.0 + static_cast<double>(i) * 2.0);
  }
  for (int i = 0; i < 8; ++i) {
    prices.push_back(120.0 - static_cast<double>(i) * 1.2);
  }
  prices.push_back(110.0);
  return prices;
}

void addFixture(std::vector<StrategyExpectancyFixture> &fixtures,
                const std::string &name, const std::string &strategy,
                std::deque<double> prices, double expected_return_fraction,
                double realized_pnl, bool has_position = false,
                long long ticks_since_last_entry = 0) {
  StrategyExpectancyFixture fixture;
  fixture.name = name;
  fixture.strategy = strategy;
  fixture.prices = std::move(prices);
  fixture.expected_return_fraction = expected_return_fraction;
  fixture.realized_pnl = realized_pnl;
  fixture.has_position = has_position;
  fixture.ticks_since_last_entry = ticks_since_last_entry;
  fixtures.push_back(std::move(fixture));
}

StrategyExpectancyMetrics summarizeRows(const std::vector<const StrategyExpectancyRow *> &rows) {
  StrategyExpectancyMetrics metrics;
  metrics.fixtures = rows.size();

  double gross_wins = 0.0;
  double gross_losses = 0.0;
  std::size_t win_count = 0;
  std::size_t loss_count = 0;
  double equity = 0.0;
  double peak_equity = 0.0;

  for (const auto *row : rows) {
    if (row->signal_type != "hold") {
      ++metrics.signals_generated;
    }
    if (row->blocked) {
      ++metrics.blocked_intents;
    }
    if (!row->filled) {
      continue;
    }

    ++metrics.trades_filled;
    metrics.total_pnl += row->realized_pnl;
    equity += row->realized_pnl;
    peak_equity = std::max(peak_equity, equity);
    metrics.max_drawdown = std::max(metrics.max_drawdown, peak_equity - equity);

    if (row->realized_pnl > 0.0) {
      gross_wins += row->realized_pnl;
      ++win_count;
    } else if (row->realized_pnl < 0.0) {
      gross_losses += -row->realized_pnl;
      ++loss_count;
    }
  }

  if (win_count > 0) {
    metrics.average_win = gross_wins / static_cast<double>(win_count);
  }
  if (loss_count > 0) {
    metrics.average_loss = gross_losses / static_cast<double>(loss_count);
  }
  if (metrics.trades_filled > 0) {
    metrics.expectancy = metrics.total_pnl / static_cast<double>(metrics.trades_filled);
  }
  if (gross_losses > 0.0) {
    metrics.profit_factor = gross_wins / gross_losses;
  } else if (gross_wins > 0.0) {
    metrics.profit_factor = std::numeric_limits<double>::infinity();
  }
  metrics.negative_expectancy_flag =
      metrics.signals_generated > 0 && metrics.trades_filled > 0 && metrics.expectancy <= 0.0;
  return metrics;
}

} // namespace

StrategyExpectancyReport evaluateStrategyExpectancy(
    const std::vector<StrategyExpectancyFixture> &fixtures) {
  StrategyExpectancyReport report;
  report.rows.reserve(fixtures.size());

  for (const auto &fixture : fixtures) {
    StrategyExpectancyRow row;
    row.fixture_name = fixture.name;
    row.strategy = fixture.strategy;

    const auto signal = evaluateStrategySignal(fixture.strategy, fixture.prices,
                                               fixture.params, fixture.has_position,
                                               fixture.ticks_since_last_entry);
    row.signal_type = signal.signal_type;
    row.signal_strength = signal.strength;

    StrategyProfitabilityInput diagnostic_input;
    diagnostic_input.strategy = fixture.strategy;
    diagnostic_input.signal_type = signal.signal_type;
    diagnostic_input.signal_strength = signal.strength;
    diagnostic_input.expected_return_available = fixture.expected_return_available;
    diagnostic_input.expected_return_fraction = fixture.expected_return_fraction;
    diagnostic_input.spread_fraction = fixture.spread_fraction;
    diagnostic_input.round_trip_fee_fraction = fixture.round_trip_fee_fraction;
    diagnostic_input.slippage_buffer_fraction = fixture.slippage_buffer_fraction;
    diagnostic_input.min_signal_strength = fixture.min_signal_strength;
    const auto diagnostic = evaluateStrategyProfitabilityDiagnostic(diagnostic_input);

    row.diagnostics_available = diagnostic.diagnostics_available;
    row.profitability_actionable = diagnostic.actionable;
    row.diagnostic_factor = diagnostic.factor;
    row.directional_expected_edge_fraction = diagnostic.directional_expected_edge_fraction;
    row.fee_adjusted_expected_return_fraction = diagnostic.fee_adjusted_expected_return_fraction;
    row.required_edge_fraction = diagnostic.required_edge_fraction;
    row.blocked = fixture.blocked || (signal.signal_type != "hold" && !diagnostic.actionable);
    row.blocked_reason = fixture.blocked ? fixture.blocked_reason : diagnostic.reason;
    row.filled = signal.signal_type != "hold" && diagnostic.actionable && !fixture.blocked;
    row.realized_pnl = row.filled ? fixture.realized_pnl : 0.0;

    report.rows.push_back(std::move(row));
  }

  std::vector<const StrategyExpectancyRow *> all_rows;
  all_rows.reserve(report.rows.size());
  std::map<std::string, std::vector<const StrategyExpectancyRow *>> rows_by_strategy;
  for (const auto &row : report.rows) {
    all_rows.push_back(&row);
    rows_by_strategy[row.strategy].push_back(&row);
  }

  report.overall = summarizeRows(all_rows);
  for (const auto &[strategy, rows] : rows_by_strategy) {
    report.by_strategy[strategy] = summarizeRows(rows);
  }
  return report;
}

std::vector<StrategyExpectancyFixture> defaultStrategyExpectancyFixtures() {
  std::vector<StrategyExpectancyFixture> fixtures;

  addFixture(fixtures, "sma-uptrend-positive-edge", "sma",
             linearSeries(100.0, 0.5, 60), 0.030, 18.0);
  addFixture(fixtures, "ema-uptrend-positive-edge", "ema",
             linearSeries(100.0, 0.5, 60), 0.028, 16.0);
  addFixture(fixtures, "rsi-oversold-positive-edge", "rsi",
             linearSeries(130.0, -1.0, 30), 0.026, 14.0);
  addFixture(fixtures, "bollinger-drop-positive-edge", "bollinger",
             bollingerExtreme(90.0), 0.024, 12.0);
  addFixture(fixtures, "macd-uptrend-positive-edge", "macd",
             linearSeries(100.0, 0.4, 80), 0.029, 15.0);
  addFixture(fixtures, "stochastic-low-positive-edge", "stochastic",
             linearSeries(120.0, -1.0, 30), 0.025, 10.0);
  addFixture(fixtures, "fibonacci-support-positive-edge", "fibonacci",
             fibonacciPullback(), 0.023, 8.0);
  addFixture(fixtures, "dca-positive-edge", "dca",
             linearSeries(100.0, 0.1, 5), 0.022, 6.0, false, 0);
  addFixture(fixtures, "buyandhold-positive-edge", "buyandhold",
             linearSeries(100.0, 0.0, 3), 0.027, 20.0, false, 0);

  // Regression fixture: high signal frequency alone is not acceptable when the
  // net expected edge is fee-negative. These rows should be generated but
  // blocked before they can become paper/live fills.
  addFixture(fixtures, "sma-uptrend-fee-negative-edge", "sma",
             linearSeries(100.0, 0.5, 60), 0.004, -9.0);
  addFixture(fixtures, "ema-uptrend-fee-negative-edge", "ema",
             linearSeries(100.0, 0.5, 60), 0.004, -8.0);

  return fixtures;
}

} // namespace trading
} // namespace trade
