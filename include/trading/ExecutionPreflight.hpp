#pragma once

#include <cstddef>
#include <string>

namespace trade {
namespace trading {

// Common fail-closed entry checks shared by live execution and live-parity paper
// evaluation. The caller remains responsible for producing the strategy signal
// and supplying authoritative account state.
struct ExecutionPreflightInputs {
  bool account_ready = true;
  bool account_entries_allowed = true;
  bool strategy_gate_passed = true;
  std::string strategy_blocker_reason = "ml_confidence_gate";
  bool existing_position = false;
  bool pending_order = false;
  std::size_t managed_positions = 0;
  std::size_t pending_entries = 0;
  std::size_t max_positions = 0;
  double allocated_usd = 0.0;
  double price = 0.0;
  double minimum_notional = 0.0;
  std::string side;
  double available_holdings = 0.0;
  double required_holdings = 0.0;
  double available_cash = 0.0;
  double estimated_fee = 0.0;
  bool require_live_execution = false;
  bool live_execution_enabled = true;
};

struct ExecutionPreflightResult {
  bool executable = false;
  std::string blocker_reason = "account_not_ready";
};

ExecutionPreflightResult evaluate_execution_preflight(const ExecutionPreflightInputs &inputs);

} // namespace trading
} // namespace trade
