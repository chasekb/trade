#include "trading/ExecutionReconciliation.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace trade {
namespace trading {

namespace {

constexpr const char *kUnknownStrategy = "unknown";
constexpr const char *kUnknownBlocker = "unknown";

struct Accumulator {
  StrategyReconciliation totals;
  std::map<std::string, BlockerBucket> blockers;
  double gross_profit = 0.0;
  double gross_loss = 0.0; // positive magnitude
};

std::string strategyKey(const std::string &strategy) {
  return strategy.empty() ? kUnknownStrategy : strategy;
}

void applySignal(Accumulator &acc, const SignalAttribution &signal) {
  ++acc.totals.signals_evaluated;
  if (!signal.signal_generated) {
    return;
  }
  ++acc.totals.signals_generated;
  if (signal.executable_intent) {
    ++acc.totals.executable_intents;
    return;
  }
  ++acc.totals.blocked_intents;
  const std::string reason =
      signal.blocker_reason.empty() ? kUnknownBlocker : signal.blocker_reason;
  auto &bucket = acc.blockers[reason];
  bucket.reason = reason;
  ++bucket.count;
  bucket.blocked_expected_return_sum += signal.fee_adjusted_expected_return;
}

void applyOutcome(Accumulator &acc, const OutcomeAttribution &outcome) {
  acc.totals.total_fees += outcome.fees;
  if (!outcome.is_closing_leg) {
    return;
  }
  ++acc.totals.closing_legs;
  acc.totals.total_pnl += outcome.realized_pnl;
  if (outcome.realized_pnl > 0.0) {
    ++acc.totals.winners;
    acc.gross_profit += outcome.realized_pnl;
  } else if (outcome.realized_pnl < 0.0) {
    ++acc.totals.losers;
    acc.gross_loss += -outcome.realized_pnl;
  }
}

StrategyReconciliation finalize(const Accumulator &acc) {
  StrategyReconciliation out = acc.totals;

  const std::size_t decided = out.winners + out.losers;
  if (decided > 0) {
    out.win_rate = 100.0 * static_cast<double>(out.winners) / static_cast<double>(decided);
    out.expectancy = out.total_pnl / static_cast<double>(decided);
  }
  if (out.winners > 0) {
    out.average_win = acc.gross_profit / static_cast<double>(out.winners);
  }
  if (out.losers > 0) {
    out.average_loss = acc.gross_loss / static_cast<double>(out.losers);
  }
  if (acc.gross_loss > 0.0) {
    out.profit_factor = acc.gross_profit / acc.gross_loss;
  } else if (acc.gross_profit > 0.0) {
    out.profit_factor = std::numeric_limits<double>::infinity();
  }
  out.negative_expectancy_flag = decided > 0 && out.expectancy < 0.0;

  if (out.signals_generated > 0) {
    out.intent_conversion_rate = static_cast<double>(out.executable_intents) /
                                 static_cast<double>(out.signals_generated);
  }
  if (out.executable_intents > 0) {
    out.outcome_coverage = static_cast<double>(out.closing_legs) /
                           static_cast<double>(out.executable_intents);
  }
  // Outcomes with no executable intent behind them mean the window is not
  // self-consistent: either it clipped the entry signals or the outcomes came
  // from a session the signal query did not cover.
  out.outcomes_unexplained = out.closing_legs > 0 && out.executable_intents == 0;

  out.blockers.reserve(acc.blockers.size());
  for (const auto &[reason, bucket] : acc.blockers) {
    BlockerBucket copy = bucket;
    if (out.blocked_intents > 0) {
      copy.share = static_cast<double>(copy.count) / static_cast<double>(out.blocked_intents);
    }
    out.blockers.push_back(copy);
  }
  std::sort(out.blockers.begin(), out.blockers.end(),
            [](const BlockerBucket &lhs, const BlockerBucket &rhs) {
              if (lhs.count != rhs.count) {
                return lhs.count > rhs.count;
              }
              return lhs.reason < rhs.reason;
            });
  if (!out.blockers.empty()) {
    out.dominant_blocker = out.blockers.front().reason;
  }
  return out;
}

} // namespace

bool closingLegFromPersistedValue(bool has_explicit_value,
                                  bool persisted_value,
                                  double gross_pnl) {
  return has_explicit_value ? persisted_value : gross_pnl != 0.0;
}

ExecutionReconciliationReport
reconcileExecution(const std::vector<SignalAttribution> &signals,
                   const std::vector<OutcomeAttribution> &outcomes) {
  std::map<std::string, Accumulator> by_strategy;
  Accumulator overall;

  for (const auto &signal : signals) {
    const std::string key = strategyKey(signal.strategy);
    by_strategy[key].totals.strategy = key;
    applySignal(by_strategy[key], signal);
    applySignal(overall, signal);
  }
  for (const auto &outcome : outcomes) {
    const std::string key = strategyKey(outcome.strategy);
    by_strategy[key].totals.strategy = key;
    applyOutcome(by_strategy[key], outcome);
    applyOutcome(overall, outcome);
  }

  ExecutionReconciliationReport report;
  for (const auto &[key, acc] : by_strategy) {
    report.by_strategy[key] = finalize(acc);
  }
  overall.totals.strategy = "overall";
  report.overall = finalize(overall);
  return report;
}

} // namespace trading
} // namespace trade
