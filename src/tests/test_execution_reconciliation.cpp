#include "trading/ExecutionReconciliation.hpp"

#include <cmath>
#include <iostream>
#include <string>
#include <vector>

using trade::trading::OutcomeAttribution;
using trade::trading::SignalAttribution;
using trade::trading::reconcileExecution;

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
         label + " (expected " + std::to_string(expected) + ", got " +
             std::to_string(actual) + ")");
}

SignalAttribution hold(const std::string &strategy) {
  SignalAttribution signal;
  signal.strategy = strategy;
  signal.symbol = "BTC-USD";
  signal.signal_generated = false;
  return signal;
}

SignalAttribution blocked(const std::string &strategy, const std::string &reason,
                          double fee_adjusted_expected_return = 0.0) {
  SignalAttribution signal;
  signal.strategy = strategy;
  signal.symbol = "BTC-USD";
  signal.signal_generated = true;
  signal.executable_intent = false;
  signal.blocker_reason = reason;
  signal.fee_adjusted_expected_return = fee_adjusted_expected_return;
  return signal;
}

SignalAttribution executable(const std::string &strategy) {
  SignalAttribution signal;
  signal.strategy = strategy;
  signal.symbol = "BTC-USD";
  signal.signal_generated = true;
  signal.executable_intent = true;
  signal.blocker_reason = "paper_fill";
  return signal;
}

OutcomeAttribution close(const std::string &strategy, double pnl, double fees = 0.0) {
  OutcomeAttribution outcome;
  outcome.strategy = strategy;
  outcome.symbol = "BTC-USD";
  outcome.realized_pnl = pnl;
  outcome.fees = fees;
  outcome.is_closing_leg = true;
  return outcome;
}

OutcomeAttribution open(const std::string &strategy, double fees) {
  OutcomeAttribution outcome;
  outcome.strategy = strategy;
  outcome.symbol = "BTC-USD";
  outcome.fees = fees;
  outcome.is_closing_leg = false;
  return outcome;
}

} // namespace

int main() {
  // Empty input is a valid, all-zero report rather than an error.
  const auto empty = reconcileExecution({}, {});
  expect(empty.by_strategy.empty(), "empty input yields no strategy rows");
  expect(empty.overall.signals_evaluated == 0, "empty input has no evaluated signals");
  expect(!empty.overall.outcomes_unexplained, "empty input is not flagged unexplained");

  std::vector<SignalAttribution> signals = {
      hold("orderbook"),
      hold("orderbook"),
      blocked("orderbook", "spot_cannot_open_short", -0.004),
      blocked("orderbook", "spot_cannot_open_short", -0.002),
      blocked("orderbook", "insufficient_cash", 0.010),
      executable("orderbook"),
      executable("orderbook"),
      blocked("rsi", "ml_confidence_gate"),
      executable("rsi"),
  };
  std::vector<OutcomeAttribution> outcomes = {
      open("orderbook", 0.50),
      close("orderbook", 12.0, 0.50),
      close("orderbook", -4.0, 0.50),
      close("rsi", -6.0, 0.25),
  };

  const auto report = reconcileExecution(signals, outcomes);

  expect(report.by_strategy.count("orderbook") == 1, "orderbook strategy bucket exists");
  expect(report.by_strategy.count("rsi") == 1, "rsi strategy bucket exists");

  const auto &ob = report.by_strategy.at("orderbook");
  expect(ob.signals_evaluated == 7, "orderbook counts every evaluated signal row");
  expect(ob.signals_generated == 5, "orderbook counts generated signals only");
  expect(ob.executable_intents == 2, "orderbook counts executable intents");
  expect(ob.blocked_intents == 3, "orderbook counts blocked intents");
  expect(ob.closing_legs == 2, "orderbook counts closing legs only");
  expect(ob.winners == 1 && ob.losers == 1, "orderbook win/loss split");
  expectNear(ob.win_rate, 50.0, 1e-9, "win_rate is a 0-100 percentage");
  expectNear(ob.average_win, 12.0, 1e-9, "orderbook average win");
  expectNear(ob.average_loss, 4.0, 1e-9, "average loss is a positive magnitude");
  expectNear(ob.expectancy, 4.0, 1e-9, "orderbook expectancy per decided trade");
  expectNear(ob.profit_factor, 3.0, 1e-9, "orderbook profit factor");
  expectNear(ob.total_pnl, 8.0, 1e-9, "orderbook total pnl");
  expectNear(ob.total_fees, 1.5, 1e-9, "fees accumulate across opening and closing legs");
  expectNear(ob.intent_conversion_rate, 2.0 / 5.0, 1e-9, "intent conversion rate");
  expectNear(ob.outcome_coverage, 1.0, 1e-9, "closing legs cover executable intents");
  expect(!ob.outcomes_unexplained, "orderbook outcomes are explained by its intents");
  expect(!ob.negative_expectancy_flag, "positive expectancy is not flagged");

  expect(ob.blockers.size() == 2, "orderbook has two blocker buckets");
  expect(ob.dominant_blocker == "spot_cannot_open_short", "dominant blocker is the largest bucket");
  expect(ob.blockers.front().reason == "spot_cannot_open_short", "blockers sort by descending count");
  expect(ob.blockers.front().count == 2, "dominant blocker count");
  expectNear(ob.blockers.front().share, 2.0 / 3.0, 1e-9, "blocker share of blocked intents");
  expectNear(ob.blockers.front().blocked_expected_return_sum, -0.006, 1e-9,
             "blocked fee-adjusted expected return accumulates per bucket");
  expectNear(ob.blockers.back().blocked_expected_return_sum, 0.010, 1e-9,
             "positive-edge intents blocked by cash are surfaced separately");

  const auto &rsi = report.by_strategy.at("rsi");
  expect(rsi.losers == 1 && rsi.winners == 0, "rsi has a single losing outcome");
  expectNear(rsi.win_rate, 0.0, 1e-9, "rsi win rate is zero");
  expectNear(rsi.profit_factor, 0.0, 1e-9, "no gross profit yields a zero profit factor");
  expect(rsi.negative_expectancy_flag, "negative expectancy is flagged");

  expect(report.overall.signals_evaluated == signals.size(), "overall covers all signal rows");
  expect(report.overall.blocked_intents == 4, "overall blocked intents across strategies");
  expect(report.overall.closing_legs == 3, "overall closing legs across strategies");
  expectNear(report.overall.total_pnl, 2.0, 1e-9, "overall total pnl");
  expect(report.overall.blockers.size() == 3, "overall keeps every blocker bucket");

  // A window that contains outcomes but no executable intents is not silently
  // reported as a clean reconciliation.
  const auto clipped = reconcileExecution({blocked("orderbook", "existing_position")},
                                          {close("orderbook", -3.0)});
  expect(clipped.by_strategy.at("orderbook").outcomes_unexplained,
         "outcomes without executable intents are flagged unexplained");
  expectNear(clipped.by_strategy.at("orderbook").outcome_coverage, 0.0, 1e-9,
             "coverage stays zero when no intent explains the outcome");

  // Missing strategy labels are bucketed explicitly instead of dropped.
  SignalAttribution unlabeled = executable("");
  const auto unknown = reconcileExecution({unlabeled}, {});
  expect(unknown.by_strategy.count("unknown") == 1, "unlabeled signals fall into the unknown bucket");

  if (failures == 0) {
    std::cout << "All execution reconciliation tests passed" << std::endl;
    return 0;
  }
  std::cerr << failures << " execution reconciliation test(s) failed" << std::endl;
  return 1;
}
