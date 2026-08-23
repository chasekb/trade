#include "trading/StrategyExpectancyHarness.hpp"

#include <cmath>
#include <iostream>
#include <limits>
#include <set>
#include <string>
#include <vector>

using trade::trading::StrategyExpectancyFixture;
using trade::trading::defaultStrategyExpectancyFixtures;
using trade::trading::evaluateStrategyExpectancy;

namespace {

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << std::endl;
    ++failures;
  }
}

} // namespace

int main() {
  const auto fixtures = defaultStrategyExpectancyFixtures();
  const auto report = evaluateStrategyExpectancy(fixtures);

  const std::set<std::string> expected_strategies = {
      "sma",        "ema",      "rsi", "bollinger", "macd",
      "stochastic", "fibonacci", "dca", "buyandhold"};

  expect(report.rows.size() == fixtures.size(), "one output row per fixture");
  expect(report.overall.fixtures == fixtures.size(), "overall fixture count");
  for (const auto &strategy : expected_strategies) {
    expect(report.by_strategy.count(strategy) == 1,
           "default harness covers strategy " + strategy);
  }

  expect(report.overall.signals_generated >= expected_strategies.size(),
         "harness counts generated signals");
  expect(report.overall.trades_filled == expected_strategies.size(),
         "fee-positive fixtures become fills");
  expect(report.overall.blocked_intents == 2,
         "fee-negative regression fixtures are blocked intents");
  expect(report.overall.expectancy > 0.0,
         "default objective baseline has positive net expectancy");
  expect(report.overall.average_win > report.overall.average_loss,
         "default baseline average win exceeds average loss");
  expect(report.overall.profit_factor > 1.0,
         "default baseline profit factor is above one");
  expect(!report.overall.negative_expectancy_flag,
         "default positive-expectancy baseline is not flagged");

  bool saw_fee_negative_block = false;
  for (const auto &row : report.rows) {
    if (row.fixture_name.find("fee-negative") != std::string::npos) {
      expect(row.signal_type != "hold", row.fixture_name + " still generated a signal");
      expect(row.blocked, row.fixture_name + " blocked before fill");
      expect(!row.filled, row.fixture_name + " not filled");
      expect(row.diagnostic_factor == "negative_fee_adjusted_edge",
             row.fixture_name + " records fee-negative diagnostic factor");
      saw_fee_negative_block = true;
    }
  }
  expect(saw_fee_negative_block, "regression fixture exercised fee-negative block");

  // Report-only diagnostics must preserve the generated signal and its
  // serialized attribution while remaining ineligible for either simulated or
  // live action. Non-finite values use the same fail-closed contract.
  std::vector<StrategyExpectancyFixture> diagnostic_fixtures;
  StrategyExpectancyFixture missing;
  missing.name = "missing-expected-return-report-only";
  missing.strategy = "buyandhold";
  missing.prices = {100.0, 100.0, 100.0};
  missing.expected_return_available = false;
  missing.expected_return_fraction = 0.050;
  diagnostic_fixtures.push_back(missing);

  StrategyExpectancyFixture nan_return = missing;
  nan_return.name = "nan-expected-return-report-only";
  nan_return.expected_return_available = true;
  nan_return.expected_return_fraction = std::numeric_limits<double>::quiet_NaN();
  diagnostic_fixtures.push_back(nan_return);

  StrategyExpectancyFixture infinite_return = missing;
  infinite_return.name = "infinite-expected-return-report-only";
  infinite_return.expected_return_available = true;
  infinite_return.expected_return_fraction = std::numeric_limits<double>::infinity();
  diagnostic_fixtures.push_back(infinite_return);

  StrategyExpectancyFixture favorable_sell;
  favorable_sell.name = "sell-positive-directional-edge";
  favorable_sell.strategy = "sma";
  favorable_sell.prices = {};
  for (int i = 0; i < 60; ++i) {
    favorable_sell.prices.push_back(130.0 - 0.5 * static_cast<double>(i));
  }
  favorable_sell.expected_return_fraction = -0.030;
  favorable_sell.realized_pnl = 7.0;
  diagnostic_fixtures.push_back(favorable_sell);

  const auto diagnostic_report = evaluateStrategyExpectancy(diagnostic_fixtures);
  expect(diagnostic_report.rows.size() == diagnostic_fixtures.size(),
         "diagnostic contract returns one serialized row per fixture");
  for (const auto &row : diagnostic_report.rows) {
    expect(std::isfinite(row.directional_expected_edge_fraction),
           row.fixture_name + " directional edge is finite for serialization");
    expect(std::isfinite(row.fee_adjusted_expected_return_fraction),
           row.fixture_name + " fee-adjusted edge is finite for serialization");
    expect(std::isfinite(row.required_edge_fraction),
           row.fixture_name + " required edge is finite for serialization");
  }

  expect(diagnostic_report.rows[0].signal_type == "buy",
         "missing return preserves simulated/live buy signal for reporting");
  expect(diagnostic_report.rows[0].blocked && !diagnostic_report.rows[0].filled,
         "missing return is report-only and cannot fill");
  expect(diagnostic_report.rows[0].diagnostic_factor == "expected_return_unavailable",
         "missing return blocker attribution is serialized");
  expect(!diagnostic_report.rows[1].profitability_actionable &&
             diagnostic_report.rows[1].diagnostic_factor == "expected_return_unavailable",
         "NaN return is unavailable and not actionable");
  expect(!diagnostic_report.rows[2].profitability_actionable &&
             diagnostic_report.rows[2].diagnostic_factor == "expected_return_unavailable",
         "infinite return is unavailable and not actionable");

  expect(diagnostic_report.rows[3].signal_type == "sell" &&
             diagnostic_report.rows[3].profitability_actionable &&
             diagnostic_report.rows[3].filled,
         "favorable fee-adjusted sell is actionable in both decision paths");

  // Confidence/profitability boundaries: equality with the minimum strength
  // and an exactly fee-neutral edge are both non-actionable.
  StrategyExpectancyFixture boundary = missing;
  boundary.name = "confidence-boundary";
  boundary.expected_return_available = true;
  boundary.expected_return_fraction = 0.017;
  boundary.min_signal_strength = 1.0;
  diagnostic_fixtures = {boundary};
  const auto boundary_report = evaluateStrategyExpectancy(diagnostic_fixtures);
  expect(boundary_report.rows.front().signal_strength == 1.0,
         "buy-and-hold confidence boundary is deterministic");
  expect(boundary_report.rows.front().profitability_actionable,
         "minimum confidence boundary is inclusive");
  boundary.expected_return_fraction = 0.017;
  boundary.round_trip_fee_fraction = 0.015;
  boundary.slippage_buffer_fraction = 0.002;
  boundary.min_signal_strength = 0.2;
  diagnostic_fixtures = {boundary};
  const auto neutral_report = evaluateStrategyExpectancy(diagnostic_fixtures);
  expect(!neutral_report.rows.front().profitability_actionable,
         "exactly fee-neutral edge is not actionable");
  expect(neutral_report.rows.front().diagnostic_factor == "negative_fee_adjusted_edge",
         "fee-neutral edge has explicit blocker attribution");

  std::vector<StrategyExpectancyFixture> high_count_loser;
  for (int i = 0; i < 5; ++i) {
    StrategyExpectancyFixture fixture;
    fixture.name = "high-count-loser-" + std::to_string(i);
    fixture.strategy = "buyandhold";
    fixture.prices = {100.0, 100.0, 100.0};
    fixture.expected_return_fraction = 0.030;
    fixture.realized_pnl = -5.0;
    high_count_loser.push_back(fixture);
  }
  const auto loser_report = evaluateStrategyExpectancy(high_count_loser);
  expect(loser_report.overall.signals_generated == high_count_loser.size(),
         "negative fixture generates many signals");
  expect(loser_report.overall.trades_filled == high_count_loser.size(),
         "negative fixture fills many trades");
  expect(loser_report.overall.expectancy < 0.0,
         "negative fixture has negative expectancy");
  expect(loser_report.overall.negative_expectancy_flag,
         "high signal count with negative expectancy is flagged");
  expect(loser_report.by_strategy.at("buyandhold").negative_expectancy_flag,
         "per-strategy negative expectancy is flagged");

  if (failures > 0) {
    std::cerr << failures << " strategy expectancy harness expectation(s) failed"
              << std::endl;
    return 1;
  }
  return 0;
}
