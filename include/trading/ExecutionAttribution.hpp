#pragma once

#include <cstddef>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace trade {
namespace trading {

// Execution attribution summarizes evaluated signals and their realized
// outcomes across strategy, symbol, side, strength, and expected-return
// dimensions, plus the diagnostic factors that explain blocked intents. It is
// a `report`-classified diagnostic (docs/STRATEGY_OBJECTIVE.md's diagnostics
// factoring contract): it never gates, sizes, or affects execution.
//
// This module is independent of ExecutionReconciliation (blocker-mix
// reconciliation by strategy/symbol only) so the two features cannot collide
// on naming or aggregation semantics. It does not compute strength or
// expected-return buckets itself: callers pass the bucket labels already
// computed upstream (`execution_analysis.strength_bucket` /
// `expected_return_bucket` for signals, `strengthBucket`/`expectedReturnBucket`
// applied to the raw `individual_trades` columns for outcomes).

// One evaluated signal row, enriched with the execution_analysis fields
// needed for dimensional attribution.
struct AttributionSignal {
  std::string strategy;
  std::string symbol;
  std::string side; // "buy" | "sell" | "" (normalized to "unknown" if empty)
  bool signal_generated = false;
  bool executable_intent = false; // only meaningful when signal_generated
  std::string blocker_reason;
  std::string diagnostic_factor;
  std::string strength_bucket;        // empty when unavailable
  std::string expected_return_bucket; // empty when unavailable
};

// One realized trade record (opening or closing leg) attributed to a signal.
struct AttributionOutcome {
  std::string strategy;
  std::string symbol;
  std::string side;
  double realized_pnl = 0.0; // net of fees; zero for opening legs
  bool is_closing_leg = false;
  // individual_trades carries no per-trade strength column, so outcomes have
  // no strength_bucket; expected_return_bucket is derived from its raw
  // expected_return column and left empty when that column is null.
  std::string expected_return_bucket;
};

// A lightweight dimensional bucket (e.g. one symbol, side, or bucket value
// under a strategy). Optional fields serialize to JSON null rather than 0
// when there is no supporting outcome evidence, so missing data is never
// presented as a real zero.
struct AttributionDimensionRow {
  std::size_t evaluated = 0;
  std::size_t blocked_intents = 0;
  std::size_t explicit_skips = 0;
  std::size_t executable_intents = 0;
  std::size_t executed_count = 0;
  std::size_t pnl_population = 0;
  std::size_t win_count = 0;
  std::size_t loss_count = 0;
  std::optional<double> win_rate_pct;
  std::optional<double> average_realized_pnl;
  // Accumulator, not part of the reported contract; controllers should not
  // serialize this field.
  double realized_pnl_sum = 0.0;
};

// A top-level reported row: one strategy, or one diagnostic-factor bucket.
struct AttributionRow {
  std::string key;
  std::size_t evaluated = 0;
  std::size_t signals_generated = 0;
  std::size_t explicit_skips = 0;
  std::size_t executable_intents = 0;
  std::size_t blocked_intents = 0;
  std::size_t executed_count = 0;
  std::size_t pnl_population = 0;
  std::size_t win_count = 0;
  std::size_t loss_count = 0;
  std::optional<double> win_rate_pct;
  std::optional<double> average_realized_pnl;
  std::optional<double> average_win_pnl;
  std::optional<double> average_loss_magnitude;
  std::optional<double> outcome_coverage;
  // True when there is no closing-leg outcome evidence for this row at all
  // (as opposed to a real, computed zero). Diagnostic-factor rows are always
  // insufficient: a diagnostic factor only ever explains a blocked intent, so
  // there is never an executed outcome to attribute a win rate to.
  bool insufficient_data = false;
  std::map<std::string, std::size_t> blocker_counts;
  std::map<std::string, std::size_t> diagnostic_factor_counts;
  // dimension name (e.g. "by_symbol") -> bucket value -> row.
  std::map<std::string, std::map<std::string, AttributionDimensionRow>> dimensions;
  // Accumulators, not part of the reported contract; controllers should not
  // serialize these fields.
  double realized_pnl_sum = 0.0;
  double win_pnl_sum = 0.0;
  double loss_pnl_sum = 0.0; // positive magnitude
};

struct ExecutionAttributionReport {
  std::vector<AttributionRow> by_strategy;
  std::vector<AttributionRow> by_diagnostic_factor;
  AttributionRow overall;
};

ExecutionAttributionReport
computeExecutionAttribution(const std::vector<AttributionSignal> &signals,
                            const std::vector<AttributionOutcome> &outcomes);

} // namespace trading
} // namespace trade
