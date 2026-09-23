#include "trading/ExecutionAttribution.hpp"

#include <algorithm>

namespace trade {
namespace trading {

namespace {

constexpr const char *kUnknown = "unknown";

std::string keyOr(const std::string &value) { return value.empty() ? kUnknown : value; }

void applySignalToDimension(AttributionDimensionRow &bucket, const AttributionSignal &signal) {
  ++bucket.evaluated;
  if (!signal.signal_generated) {
    ++bucket.explicit_skips;
    return;
  }
  if (signal.executable_intent) {
    ++bucket.executable_intents;
  } else {
    ++bucket.blocked_intents;
  }
}

void applyOutcomeToDimension(AttributionDimensionRow &bucket, const AttributionOutcome &outcome) {
  ++bucket.executed_count;
  if (!outcome.is_closing_leg) {
    return;
  }
  ++bucket.pnl_population;
  bucket.realized_pnl_sum += outcome.realized_pnl;
  if (outcome.realized_pnl > 0.0) {
    ++bucket.win_count;
  } else if (outcome.realized_pnl < 0.0) {
    ++bucket.loss_count;
  }
}

void finalizeDimension(AttributionDimensionRow &bucket) {
  const std::size_t decided = bucket.win_count + bucket.loss_count;
  if (decided > 0) {
    bucket.win_rate_pct = 100.0 * static_cast<double>(bucket.win_count) / static_cast<double>(decided);
  }
  if (bucket.pnl_population > 0) {
    bucket.average_realized_pnl = bucket.realized_pnl_sum / static_cast<double>(bucket.pnl_population);
  }
}

struct DiagnosticAccumulator {
  std::size_t evaluated = 0;
  std::size_t blocked_intents = 0;
};

// Per-strategy signal/outcome accumulation, including the by_symbol/by_side/
// by_strength_bucket/by_expected_return_bucket dimensions. Signals and
// outcomes are joined only by shared dimension key (strategy, symbol, side,
// bucket) rather than by a literal per-row id, matching the join style
// ExecutionReconciliation already uses for its strategy/symbol aggregation.
struct StrategyAccumulator {
  AttributionRow row;
  std::map<std::string, AttributionDimensionRow> by_symbol;
  std::map<std::string, AttributionDimensionRow> by_side;
  std::map<std::string, AttributionDimensionRow> by_strength_bucket;
  std::map<std::string, AttributionDimensionRow> by_expected_return_bucket;
};

void applySignal(StrategyAccumulator &acc, const AttributionSignal &signal) {
  auto &row = acc.row;
  ++row.evaluated;
  if (!signal.signal_generated) {
    ++row.explicit_skips;
  } else {
    ++row.signals_generated;
    if (signal.executable_intent) {
      ++row.executable_intents;
    } else {
      ++row.blocked_intents;
      ++row.blocker_counts[keyOr(signal.blocker_reason)];
      ++row.diagnostic_factor_counts[keyOr(signal.diagnostic_factor)];
    }
  }

  applySignalToDimension(acc.by_symbol[keyOr(signal.symbol)], signal);
  applySignalToDimension(acc.by_side[keyOr(signal.side)], signal);
  if (!signal.strength_bucket.empty()) {
    applySignalToDimension(acc.by_strength_bucket[signal.strength_bucket], signal);
  }
  if (!signal.expected_return_bucket.empty()) {
    applySignalToDimension(acc.by_expected_return_bucket[signal.expected_return_bucket], signal);
  }
}

void applyOutcome(StrategyAccumulator &acc, const AttributionOutcome &outcome) {
  auto &row = acc.row;
  ++row.executed_count;
  if (outcome.is_closing_leg) {
    ++row.pnl_population;
    row.realized_pnl_sum += outcome.realized_pnl;
    if (outcome.realized_pnl > 0.0) {
      ++row.win_count;
      row.win_pnl_sum += outcome.realized_pnl;
    } else if (outcome.realized_pnl < 0.0) {
      ++row.loss_count;
      row.loss_pnl_sum += -outcome.realized_pnl;
    }
  }

  applyOutcomeToDimension(acc.by_symbol[keyOr(outcome.symbol)], outcome);
  applyOutcomeToDimension(acc.by_side[keyOr(outcome.side)], outcome);
  if (!outcome.expected_return_bucket.empty()) {
    applyOutcomeToDimension(acc.by_expected_return_bucket[outcome.expected_return_bucket], outcome);
  }
  // individual_trades carries no per-trade strength column, so
  // by_strength_bucket never receives outcome evidence; its win rate and
  // average realized PnL stay null rather than being approximated from an
  // unrelated confidence metric.
}

AttributionRow finalizeRow(StrategyAccumulator &acc) {
  AttributionRow row = acc.row;

  const std::size_t decided = row.win_count + row.loss_count;
  if (decided > 0) {
    row.win_rate_pct = 100.0 * static_cast<double>(row.win_count) / static_cast<double>(decided);
  }
  if (row.pnl_population > 0) {
    row.average_realized_pnl = row.realized_pnl_sum / static_cast<double>(row.pnl_population);
  }
  if (row.win_count > 0) {
    row.average_win_pnl = row.win_pnl_sum / static_cast<double>(row.win_count);
  }
  if (row.loss_count > 0) {
    row.average_loss_magnitude = row.loss_pnl_sum / static_cast<double>(row.loss_count);
  }
  if (row.executable_intents > 0) {
    row.outcome_coverage =
        static_cast<double>(row.pnl_population) / static_cast<double>(row.executable_intents);
  }
  row.insufficient_data = row.pnl_population == 0;

  for (auto &[key, bucket] : acc.by_symbol) {
    (void)key;
    finalizeDimension(bucket);
  }
  for (auto &[key, bucket] : acc.by_side) {
    (void)key;
    finalizeDimension(bucket);
  }
  for (auto &[key, bucket] : acc.by_strength_bucket) {
    (void)key;
    finalizeDimension(bucket);
  }
  for (auto &[key, bucket] : acc.by_expected_return_bucket) {
    (void)key;
    finalizeDimension(bucket);
  }

  row.dimensions["by_symbol"] = acc.by_symbol;
  row.dimensions["by_side"] = acc.by_side;
  row.dimensions["by_strength_bucket"] = acc.by_strength_bucket;
  row.dimensions["by_expected_return_bucket"] = acc.by_expected_return_bucket;

  return row;
}

} // namespace

ExecutionAttributionReport
computeExecutionAttribution(const std::vector<AttributionSignal> &signals,
                            const std::vector<AttributionOutcome> &outcomes) {
  std::map<std::string, StrategyAccumulator> by_strategy;
  StrategyAccumulator overall_acc;
  std::map<std::string, DiagnosticAccumulator> by_diagnostic;

  for (const auto &signal : signals) {
    const std::string key = keyOr(signal.strategy);
    by_strategy[key].row.key = key;
    applySignal(by_strategy[key], signal);
    applySignal(overall_acc, signal);

    if (signal.signal_generated && !signal.executable_intent) {
      auto &diag = by_diagnostic[keyOr(signal.diagnostic_factor)];
      ++diag.evaluated;
      ++diag.blocked_intents;
    }
  }
  for (const auto &outcome : outcomes) {
    const std::string key = keyOr(outcome.strategy);
    by_strategy[key].row.key = key;
    applyOutcome(by_strategy[key], outcome);
    applyOutcome(overall_acc, outcome);
  }

  ExecutionAttributionReport report;
  report.by_strategy.reserve(by_strategy.size());
  for (auto &[key, acc] : by_strategy) {
    (void)key;
    report.by_strategy.push_back(finalizeRow(acc));
  }
  std::sort(report.by_strategy.begin(), report.by_strategy.end(),
            [](const AttributionRow &a, const AttributionRow &b) { return a.key < b.key; });

  report.by_diagnostic_factor.reserve(by_diagnostic.size());
  for (const auto &[factor, diag] : by_diagnostic) {
    AttributionRow row;
    row.key = factor;
    row.evaluated = diag.evaluated;
    row.blocked_intents = diag.blocked_intents;
    // A diagnostic factor only ever attaches to a blocked intent, so there is
    // never a closing-leg outcome to attribute a win rate or realized PnL to.
    row.insufficient_data = true;
    report.by_diagnostic_factor.push_back(std::move(row));
  }

  overall_acc.row.key = "overall";
  report.overall = finalizeRow(overall_acc);

  return report;
}

} // namespace trading
} // namespace trade
