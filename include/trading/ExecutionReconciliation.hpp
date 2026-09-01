#pragma once

#include <map>
#include <optional>
#include <string>
#include <vector>

namespace trade {
namespace trading {

// Stable, storage-facing vocabulary for one terminal attribution per signal
// or paper/live intent. Keep the string spellings in sync with the JSON/API
// contract; unknown input is rejected rather than treated as executed.
enum class AttributionStatus { executed, blocked, skipped };
enum class RuntimeMode { simulated, live_parity, live };
enum class AttributionSide { buy, sell, none };

enum class BlockerCategory {
  none,
  max_positions,
  pending_order,
  spot_cannot_short,
  minimum_notional,
  insufficient_cash,
  live_execution_disabled,
  existing_holding,
  ml_or_profitability_gate,
  stop_or_take_profit_close,
  stale_or_missing_data,
  unknown
};

enum class DiagnosticFactor {
  none,
  missing_expected_return,
  negative_fee_adjusted_edge,
  below_required_edge,
  weak_strength,
  account_or_exchange_blocker,
  exit_risk_rule,
  unknown
};

struct ObjectiveImpact {
  // Fractions are prediction-time values; realized_pnl is net dollars.
  double expected_return = 0.0;
  double fee_adjusted_expected_return = 0.0;
  double realized_pnl = 0.0;
  double fees = 0.0;
  double net_objective_impact = 0.0;
};

struct SignalOutcomeAttribution {
  // signal_id is the idempotency key. session_id is an opaque session key;
  // neither this type nor its metadata may contain credentials or balances.
  std::string signal_id;
  std::string session_id;
  std::string strategy;
  std::string symbol;
  AttributionStatus status = AttributionStatus::skipped;
  BlockerCategory blocker = BlockerCategory::unknown;
  DiagnosticFactor diagnostic = DiagnosticFactor::unknown;
  AttributionSide side = AttributionSide::none;
  double strength = 0.0;
  double expected_return = 0.0;
  std::string strength_bucket;
  std::string expected_return_bucket;
  RuntimeMode mode = RuntimeMode::simulated;
  long long timestamp_epoch_seconds = 0;
  std::string runtime_window;
  ObjectiveImpact objective;
  // Short, redacted diagnostic labels only (for example, quote_unavailable).
  std::map<std::string, std::string> safe_metadata;
};

const char *toString(AttributionStatus value);
const char *toString(RuntimeMode value);
const char *toString(AttributionSide value);
const char *toString(BlockerCategory value);
const char *toString(DiagnosticFactor value);

// Bucket boundaries are strength [0,1]: weak < .30, medium [.30,.70), strong
// [.70,1]. Expected return is a fraction: negative < 0, neutral [0,.001),
// positive [0.001,.01), and high >= .01. Non-finite/out-of-range values fail.
std::string strengthBucket(double strength);
std::string expectedReturnBucket(double expected_return);

// Returns an error for incomplete/unsafe records. Callers must not persist or
// submit an intent when this returns a value. Missing optional legacy values
// are handled by the adapter below, not by weakening this validation.
std::optional<std::string> validateSignalOutcome(const SignalOutcomeAttribution &outcome);

// Additive compatibility adapter for existing signal rows. Legacy rows with
// no terminal outcome become an explicit skipped/unknown record and therefore
// remain visible in reconciliation instead of being counted as executed.
SignalOutcomeAttribution legacySkippedOutcome(const std::string &signal_id,
                                              const std::string &session_id,
                                              const std::string &strategy,
                                              const std::string &symbol,
                                              RuntimeMode mode);

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
