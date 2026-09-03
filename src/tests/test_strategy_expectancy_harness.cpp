#include "trading/StrategyExpectancyHarness.hpp"

#include <cmath>
#include <iostream>
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
