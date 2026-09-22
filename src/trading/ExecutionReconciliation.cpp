#include "trading/ExecutionReconciliation.hpp"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <limits>

namespace trade {
namespace trading {

const char *toString(const AttributionStatus value) {
  switch (value) {
  case AttributionStatus::executed: return "executed";
  case AttributionStatus::blocked: return "blocked";
  case AttributionStatus::skipped: return "skipped";
  }
  return "unknown";
}

const char *toString(const RuntimeMode value) {
  switch (value) {
  case RuntimeMode::simulated: return "simulated";
  case RuntimeMode::live_parity: return "live_parity";
  case RuntimeMode::live: return "live";
  }
  return "unknown";
}

const char *toString(const AttributionSide value) {
  switch (value) {
  case AttributionSide::buy: return "buy";
  case AttributionSide::sell: return "sell";
  case AttributionSide::none: return "none";
  }
  return "unknown";
}

const char *toString(const BlockerCategory value) {
  switch (value) {
  case BlockerCategory::none: return "none";
  case BlockerCategory::max_positions: return "max_positions";
  case BlockerCategory::pending_order: return "pending_order";
  case BlockerCategory::spot_cannot_short: return "spot_cannot_short";
  case BlockerCategory::minimum_notional: return "minimum_notional";
  case BlockerCategory::insufficient_cash: return "insufficient_cash";
  case BlockerCategory::live_execution_disabled: return "live_execution_disabled";
  case BlockerCategory::existing_holding: return "existing_holding";
  case BlockerCategory::ml_or_profitability_gate: return "ml_or_profitability_gate";
  case BlockerCategory::stop_or_take_profit_close: return "stop_or_take_profit_close";
  case BlockerCategory::stale_or_missing_data: return "stale_or_missing_data";
  case BlockerCategory::unknown: return "unknown";
  }
  return "unknown";
}

const char *toString(const DiagnosticFactor value) {
  switch (value) {
  case DiagnosticFactor::none: return "none";
  case DiagnosticFactor::missing_expected_return: return "missing_expected_return";
  case DiagnosticFactor::negative_fee_adjusted_edge: return "negative_fee_adjusted_edge";
  case DiagnosticFactor::below_required_edge: return "below_required_edge";
  case DiagnosticFactor::weak_strength: return "weak_strength";
  case DiagnosticFactor::account_or_exchange_blocker: return "account_or_exchange_blocker";
  case DiagnosticFactor::exit_risk_rule: return "exit_risk_rule";
  case DiagnosticFactor::unknown: return "unknown";
  }
  return "unknown";
}

std::string strengthBucket(const double strength) {
  if (!std::isfinite(strength) || strength < 0.0 || strength > 1.0) return "invalid";
  if (strength < 0.30) return "weak";
  if (strength < 0.70) return "medium";
  return "strong";
}

std::string expectedReturnBucket(const double expected_return) {
  if (!std::isfinite(expected_return)) return "invalid";
  if (expected_return < 0.0) return "negative";
  if (expected_return < 0.001) return "neutral";
  if (expected_return < 0.01) return "positive";
  return "high";
}

namespace {

bool validStatus(const AttributionStatus value) {
  return value == AttributionStatus::executed ||
         value == AttributionStatus::blocked || value == AttributionStatus::skipped;
}

bool validMode(const RuntimeMode value) {
  return value == RuntimeMode::simulated || value == RuntimeMode::live_parity ||
         value == RuntimeMode::live;
}

bool validSide(const AttributionSide value) {
  return value == AttributionSide::buy || value == AttributionSide::sell ||
         value == AttributionSide::none;
}

bool validBlocker(const BlockerCategory value) {
  return value >= BlockerCategory::none && value <= BlockerCategory::unknown;
}

bool validDiagnostic(const DiagnosticFactor value) {
  return value >= DiagnosticFactor::none && value <= DiagnosticFactor::unknown;
}

} // namespace

std::optional<std::string>
validateSignalOutcome(const SignalOutcomeAttribution &outcome) {
  const auto fail = [](const char *message) -> std::optional<std::string> {
    return std::string(message);
  };
  if (outcome.signal_id.empty() || outcome.session_id.empty() ||
      outcome.strategy.empty() || outcome.symbol.empty()) {
    return fail("signal_id, session_id, strategy, and symbol are required");
  }
  if (outcome.timestamp_epoch_seconds <= 0 || outcome.runtime_window.empty()) {
    return fail("positive timestamp and runtime_window are required");
  }
  if (!validStatus(outcome.status) || !validMode(outcome.mode) ||
      !validSide(outcome.side) || !validBlocker(outcome.blocker) ||
      !validDiagnostic(outcome.diagnostic)) {
    return fail("status, mode, side, blocker, or diagnostic is invalid");
  }
  if (strengthBucket(outcome.strength) == "invalid" ||
      outcome.strength_bucket != strengthBucket(outcome.strength)) {
    return fail("strength or strength_bucket is invalid");
  }
  if (expectedReturnBucket(outcome.expected_return) == "invalid" ||
      outcome.expected_return_bucket != expectedReturnBucket(outcome.expected_return)) {
    return fail("expected_return or expected_return_bucket is invalid");
  }
  if (!std::isfinite(outcome.objective.expected_return) ||
      !std::isfinite(outcome.objective.fee_adjusted_expected_return) ||
      !std::isfinite(outcome.objective.realized_pnl) ||
      !std::isfinite(outcome.objective.fees) ||
      !std::isfinite(outcome.objective.net_objective_impact) || outcome.objective.fees < 0.0) {
    return fail("objective impact contains a non-finite or negative fee");
  }
  if (outcome.status == AttributionStatus::executed &&
      (outcome.side == AttributionSide::none || outcome.blocker != BlockerCategory::none)) {
    return fail("executed outcomes require a side and no blocker");
  }
  if (outcome.status == AttributionStatus::blocked &&
      (outcome.blocker == BlockerCategory::none ||
       outcome.side == AttributionSide::none)) {
    return fail("blocked outcomes require a blocker category and side");
  }
  if (outcome.status == AttributionStatus::skipped &&
      outcome.side != AttributionSide::none) {
    return fail("skipped outcomes must not carry an order side");
  }
  for (const auto &[key, value] : outcome.safe_metadata) {
    if (key.empty() || key.size() > 64 || value.size() > 256) {
      return fail("safe metadata is outside its bounded shape");
    }
    std::string lowered = key + " " + value;
    std::transform(lowered.begin(), lowered.end(), lowered.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    for (const char *secret_word : {"secret", "password", "token", "credential", "private_key", "balance"}) {
      if (lowered.find(secret_word) != std::string::npos) {
        return fail("safe metadata contains a forbidden sensitive label");
      }
    }
  }
  return std::nullopt;
}

SignalOutcomeAttribution legacySkippedOutcome(const std::string &signal_id,
                                              const std::string &session_id,
                                              const std::string &strategy,
                                              const std::string &symbol,
                                              const RuntimeMode mode) {
  SignalOutcomeAttribution outcome;
  outcome.signal_id = signal_id;
  outcome.session_id = session_id;
  outcome.strategy = strategy;
  outcome.symbol = symbol;
  outcome.status = AttributionStatus::skipped;
  outcome.blocker = BlockerCategory::unknown;
  outcome.diagnostic = DiagnosticFactor::unknown;
  outcome.mode = mode;
  outcome.timestamp_epoch_seconds = 1;
  outcome.runtime_window = "legacy";
  outcome.strength_bucket = strengthBucket(outcome.strength);
  outcome.expected_return_bucket = expectedReturnBucket(outcome.expected_return);
  outcome.safe_metadata.emplace("compatibility", "legacy_signal_without_terminal_outcome");
  return outcome;
}

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

std::string symbolKey(const std::string &symbol) {
  return symbol.empty() ? "unknown" : symbol;
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

ExecutionReconciliationReport
reconcileExecution(const std::vector<SignalAttribution> &signals,
                   const std::vector<OutcomeAttribution> &outcomes) {
  std::map<std::string, Accumulator> by_strategy;
  std::map<std::string, Accumulator> by_symbol;
  Accumulator overall;

  for (const auto &signal : signals) {
    const std::string key = strategyKey(signal.strategy);
    const std::string symbol = symbolKey(signal.symbol);
    by_strategy[key].totals.strategy = key;
    applySignal(by_strategy[key], signal);
    by_symbol[symbol].totals.strategy = symbol;
    applySignal(by_symbol[symbol], signal);
    applySignal(overall, signal);
  }
  for (const auto &outcome : outcomes) {
    const std::string key = strategyKey(outcome.strategy);
    const std::string symbol = symbolKey(outcome.symbol);
    by_strategy[key].totals.strategy = key;
    applyOutcome(by_strategy[key], outcome);
    by_symbol[symbol].totals.strategy = symbol;
    applyOutcome(by_symbol[symbol], outcome);
    applyOutcome(overall, outcome);
  }

  ExecutionReconciliationReport report;
  for (const auto &[key, acc] : by_strategy) {
    report.by_strategy[key] = finalize(acc);
  }
  for (const auto &[key, acc] : by_symbol) {
    report.by_symbol[key] = finalize(acc);
  }
  overall.totals.strategy = "overall";
  report.overall = finalize(overall);
  return report;
}

} // namespace trading
} // namespace trade
