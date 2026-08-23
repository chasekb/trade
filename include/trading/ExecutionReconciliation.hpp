#pragma once

#include <map>
#include <string>
#include <vector>

namespace trade {
namespace trading {

// Reconciliation of generated signals to execution outcomes, bucketed by
// strategy and blocker reason. This is the aggregation half of
// "attribute execution blockers and outcomes by strategy": callers supply the
// signal attributions written by the trading services (`execution_analysis`)
// and the realized trade outcomes, and receive per-strategy expectancy plus
// the blocker mix that explains the intents that never became fills.
//
// The module is deliberately free of JSON/database types so it can be unit
// tested without the server toolchain; serialization lives in the controller.

struct SignalAttribution {
  std::string strategy;
  std::string symbol;
  // A signal row exists for every evaluated tick, including holds.
  bool signal_generated = false;
  bool executable_intent = false;
  std::string blocker_reason;
  std::string intended_side;
  std::string diagnostic_factor;
  double expected_return = 0.0;
  double fee_adjusted_expected_return = 0.0;
};

struct OutcomeAttribution {
  std::string strategy;
  std::string symbol;
  // Net realized PnL after fees for a closing leg. Opening legs carry zero
  // realized PnL and are excluded from win/loss denominators, matching the
  // backend win-rate convention.
  double realized_pnl = 0.0;
  double fees = 0.0;
  bool is_closing_leg = false;
};

struct BlockerBucket {
  std::string reason;
  std::size_t count = 0;
  double share = 0.0; // fraction of blocked intents for the strategy, 0-1
  double blocked_expected_return_sum = 0.0;
};

struct StrategyReconciliation {
  std::string strategy;
  std::size_t signals_evaluated = 0;
  std::size_t signals_generated = 0;
  std::size_t executable_intents = 0;
  std::size_t blocked_intents = 0;
  std::size_t closing_legs = 0;
  std::size_t winners = 0;
  std::size_t losers = 0;
  double win_rate = 0.0; // 0-100, matching the backend serialization contract
  double average_win = 0.0;
  double average_loss = 0.0; // reported as a positive magnitude
  double expectancy = 0.0;
  double profit_factor = 0.0;
  double total_pnl = 0.0;
  double total_fees = 0.0;
  double intent_conversion_rate = 0.0; // executable intents / generated signals
  // Closing legs divided by executable intents. Below 1.0 means intents are
  // still open (or unaccounted); above 1.0 means outcomes exist that this
  // window's signals do not explain.
  double outcome_coverage = 0.0;
  bool outcomes_unexplained = false;
  bool negative_expectancy_flag = false;
  std::vector<BlockerBucket> blockers; // descending by count, then reason
  std::string dominant_blocker;
};

struct ExecutionReconciliationReport {
  std::map<std::string, StrategyReconciliation> by_strategy;
  // Keep symbol-level attribution alongside strategy totals so a selected
  // universe can be reconciled without hiding a blocked or unfilled symbol.
  std::map<std::string, StrategyReconciliation> by_symbol;
  StrategyReconciliation overall;
};

ExecutionReconciliationReport
reconcileExecution(const std::vector<SignalAttribution> &signals,
                   const std::vector<OutcomeAttribution> &outcomes);

} // namespace trading
} // namespace trade
