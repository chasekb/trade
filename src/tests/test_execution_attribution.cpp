#include "trading/ExecutionAttribution.hpp"

#include <cmath>
#include <iostream>
#include <string>
#include <vector>

using trade::trading::AttributionDimensionRow;
using trade::trading::AttributionOutcome;
using trade::trading::AttributionRow;
using trade::trading::AttributionSignal;
using trade::trading::computeExecutionAttribution;

namespace {

int failures = 0;

void expect(bool condition, const std::string &label) {
  if (!condition) {
    std::cerr << "FAIL: " << label << std::endl;
    ++failures;
  }
}

void expectNear(double actual, double expected, double tolerance, const std::string &label) {
  expect(std::fabs(actual - expected) <= tolerance,
         label + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
}

const AttributionRow *findRow(const std::vector<AttributionRow> &rows, const std::string &key) {
  for (const auto &row : rows) {
    if (row.key == key) return &row;
  }
  return nullptr;
}

AttributionSignal hold(const std::string &strategy, const std::string &symbol = "BTC-USD") {
  AttributionSignal signal;
  signal.strategy = strategy;
  signal.symbol = symbol;
  signal.signal_generated = false;
  return signal;
}

AttributionSignal blocked(const std::string &strategy, const std::string &blocker_reason,
                          const std::string &diagnostic_factor, const std::string &side = "buy",
                          const std::string &strength_bucket = "weak") {
  AttributionSignal signal;
  signal.strategy = strategy;
  signal.symbol = "BTC-USD";
  signal.signal_generated = true;
  signal.executable_intent = false;
  signal.blocker_reason = blocker_reason;
  signal.diagnostic_factor = diagnostic_factor;
  signal.side = side;
  signal.strength_bucket = strength_bucket;
  signal.expected_return_bucket = "negative";
  return signal;
}

AttributionSignal executable(const std::string &strategy, const std::string &symbol,
                             const std::string &side, const std::string &strength_bucket,
                             const std::string &expected_return_bucket) {
  AttributionSignal signal;
  signal.strategy = strategy;
  signal.symbol = symbol;
  signal.signal_generated = true;
  signal.executable_intent = true;
  signal.side = side;
  signal.strength_bucket = strength_bucket;
  signal.expected_return_bucket = expected_return_bucket;
  return signal;
}

AttributionOutcome close(const std::string &strategy, const std::string &symbol, const std::string &side,
                         double realized_pnl, const std::string &expected_return_bucket) {
  AttributionOutcome outcome;
  outcome.strategy = strategy;
  outcome.symbol = symbol;
  outcome.side = side;
  outcome.realized_pnl = realized_pnl;
  outcome.is_closing_leg = true;
  outcome.expected_return_bucket = expected_return_bucket;
  return outcome;
}

AttributionOutcome open(const std::string &strategy, const std::string &symbol, const std::string &side) {
  AttributionOutcome outcome;
  outcome.strategy = strategy;
  outcome.symbol = symbol;
  outcome.side = side;
  outcome.is_closing_leg = false;
  return outcome;
}

const AttributionDimensionRow &dim(const AttributionRow &row, const std::string &dimension,
                                   const std::string &bucket) {
  return row.dimensions.at(dimension).at(bucket);
}

} // namespace

int main() {
  // Empty input yields a valid, all-zero, non-crashing report.
  const auto empty = computeExecutionAttribution({}, {});
  expect(empty.by_strategy.empty(), "empty input yields no strategy rows");
  expect(empty.by_diagnostic_factor.empty(), "empty input yields no diagnostic-factor rows");
  expect(empty.overall.evaluated == 0, "empty input has no evaluated signals");
  expect(empty.overall.insufficient_data, "empty input has no outcome evidence");

  std::vector<AttributionSignal> signals = {
      hold("orderbook"),
      blocked("orderbook", "pending_order", "account_or_exchange_blocker", "sell", "weak"),
      blocked("orderbook", "spot_cannot_short", "weak_strength", "sell", "weak"),
      executable("orderbook", "BTC-USD", "buy", "strong", "high"),
      executable("orderbook", "ETH-USD", "buy", "medium", "high"),
  };
  std::vector<AttributionOutcome> outcomes = {
      close("orderbook", "BTC-USD", "buy", 12.0, "high"),
      close("orderbook", "ETH-USD", "buy", -4.0, "high"),
      open("orderbook", "BTC-USD", "buy"),
  };

  const auto report = computeExecutionAttribution(signals, outcomes);
  const auto *orderbook = findRow(report.by_strategy, "orderbook");
  expect(orderbook != nullptr, "orderbook strategy row exists");

  expect(orderbook->evaluated == 5, "orderbook counts every evaluated signal row");
  expect(orderbook->signals_generated == 4, "orderbook counts generated signals only");
  expect(orderbook->explicit_skips == 1, "orderbook counts explicit holds as skips");
  expect(orderbook->executable_intents == 2, "orderbook counts executable intents");
  expect(orderbook->blocked_intents == 2, "orderbook counts blocked intents");
  expect(orderbook->executed_count == 3, "executed_count includes opening and closing legs");
  expect(orderbook->pnl_population == 2, "pnl_population counts closing legs only");
  expect(orderbook->win_count == 1 && orderbook->loss_count == 1, "orderbook win/loss split");
  expect(orderbook->win_rate_pct.has_value(), "win rate is present with closing-leg evidence");
  expectNear(*orderbook->win_rate_pct, 50.0, 1e-9, "win_rate_pct is a 0-100 percentage");
  expect(orderbook->average_realized_pnl.has_value(), "average realized pnl is present");
  expectNear(*orderbook->average_realized_pnl, 4.0, 1e-9, "average realized pnl over closing legs");
  expect(!orderbook->insufficient_data, "orderbook has closing-leg evidence");

  expect(orderbook->blocker_counts.at("pending_order") == 1, "pending_order blocker counted");
  expect(orderbook->blocker_counts.at("spot_cannot_short") == 1, "spot_cannot_short blocker counted");
  expect(orderbook->diagnostic_factor_counts.at("account_or_exchange_blocker") == 1,
         "account_or_exchange_blocker diagnostic counted");
  expect(orderbook->diagnostic_factor_counts.at("weak_strength") == 1,
         "weak_strength diagnostic counted");

  // by_symbol dimension gets a real win rate from outcomes joined on symbol.
  const auto &btc = dim(*orderbook, "by_symbol", "BTC-USD");
  expect(btc.win_count == 1 && btc.loss_count == 0, "BTC-USD symbol dimension win count");
  expect(btc.win_rate_pct.has_value(), "BTC-USD symbol dimension has a win rate");
  const auto &eth = dim(*orderbook, "by_symbol", "ETH-USD");
  expect(eth.loss_count == 1, "ETH-USD symbol dimension loss count");

  // by_side dimension: both outcomes are "buy", so a real win rate exists.
  const auto &buySide = dim(*orderbook, "by_side", "buy");
  expect(buySide.win_count == 1 && buySide.loss_count == 1, "buy side dimension win/loss split");
  expect(buySide.win_rate_pct.has_value(), "buy side dimension has a win rate");
  const auto &sellSide = dim(*orderbook, "by_side", "sell");
  expect(!sellSide.win_rate_pct.has_value(),
         "sell side dimension has no outcome evidence and stays null, not zero");

  // by_expected_return_bucket dimension: outcomes carry expected_return, so a
  // real win rate is attributable.
  const auto &highBucket = dim(*orderbook, "by_expected_return_bucket", "high");
  expect(highBucket.win_count == 1 && highBucket.loss_count == 1,
         "expected-return bucket dimension aggregates outcomes");

  // by_strength_bucket dimension has signal-side counts but no outcome
  // evidence (individual_trades carries no per-trade strength), so its win
  // rate must remain null rather than being coerced to zero.
  const auto &strongBucket = dim(*orderbook, "by_strength_bucket", "strong");
  expect(strongBucket.evaluated == 1, "strong strength bucket counts its signal");
  expect(!strongBucket.win_rate_pct.has_value(),
         "strength bucket has no outcome linkage and stays null");
  expect(!strongBucket.average_realized_pnl.has_value(),
         "strength bucket average realized pnl stays null");

  // Diagnostic-factor rows only ever explain blocked intents, so they carry
  // no outcome evidence at all.
  const auto *weakStrength = findRow(report.by_diagnostic_factor, "weak_strength");
  expect(weakStrength != nullptr, "weak_strength diagnostic-factor row exists");
  expect(weakStrength->evaluated == 1 && weakStrength->blocked_intents == 1,
         "weak_strength diagnostic-factor counts");
  expect(weakStrength->insufficient_data, "diagnostic-factor rows are always insufficient_data");
  expect(!weakStrength->win_rate_pct.has_value(), "diagnostic-factor rows never report a win rate");

  expect(report.overall.evaluated == signals.size(), "overall covers every evaluated signal row");
  expect(report.overall.pnl_population == 2, "overall pnl population across strategies");

  // Missing strategy/symbol/side labels fall into an explicit "unknown"
  // bucket instead of being dropped.
  AttributionSignal unlabeled;
  unlabeled.signal_generated = true;
  unlabeled.executable_intent = true;
  const auto unknownReport = computeExecutionAttribution({unlabeled}, {});
  expect(findRow(unknownReport.by_strategy, "unknown") != nullptr,
         "unlabeled signals fall into the unknown strategy bucket");

  if (failures == 0) {
    std::cout << "All execution attribution tests passed" << std::endl;
    return 0;
  }
  std::cerr << failures << " execution attribution test(s) failed" << std::endl;
  return 1;
}
