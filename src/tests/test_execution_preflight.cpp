#include "trading/ExecutionPreflight.hpp"

#include <iostream>
#include <string>

namespace {

trade::trading::ExecutionPreflightInputs baseline() {
  trade::trading::ExecutionPreflightInputs inputs;
  inputs.max_positions = 5;
  inputs.allocated_usd = 100.0;
  inputs.price = 100.0;
  inputs.minimum_notional = 10.0;
  inputs.side = "buy";
  inputs.available_cash = 1000.0;
  inputs.estimated_fee = 1.0;
  inputs.require_live_execution = true;
  inputs.live_execution_enabled = true;
  return inputs;
}

bool expects(const trade::trading::ExecutionPreflightInputs &inputs,
             const std::string &reason) {
  const auto result = trade::trading::evaluate_execution_preflight(inputs);
  return !result.executable && result.blocker_reason == reason;
}

} // namespace

int main() {
  const auto ready = baseline();
  const auto live = trade::trading::evaluate_execution_preflight(ready);
  auto parity_inputs = ready;
  parity_inputs.require_live_execution = false;
  const auto parity = trade::trading::evaluate_execution_preflight(parity_inputs);
  if (!live.executable || !parity.executable || live.blocker_reason != "paper_fill" ||
      parity.blocker_reason != "paper_fill") {
    std::cerr << "Live and live-parity must agree on a passing fixture\n";
    return 1;
  }

  auto input = ready;
  input.account_ready = false;
  if (!expects(input, "account_not_ready")) return 1;
  input = ready;
  input.account_entries_allowed = false;
  if (!expects(input, "account_position_management_disabled")) return 1;
  input = ready;
  input.strategy_gate_passed = false;
  if (!expects(input, "ml_confidence_gate")) return 1;
  input = ready;
  input.existing_position = true;
  if (!expects(input, "existing_position")) return 1;
  input = ready;
  input.pending_order = true;
  if (!expects(input, "pending_order")) return 1;
  input = ready;
  input.managed_positions = 5;
  if (!expects(input, "max_positions")) return 1;
  input = ready;
  input.allocated_usd = 0.0;
  if (!expects(input, "nonpositive_position_size_or_price")) return 1;
  input = ready;
  input.allocated_usd = 5.0;
  if (!expects(input, "below_minimum_notional")) return 1;
  input = ready;
  input.side = "sell";
  if (!expects(input, "insufficient_holdings")) return 1;
  input.available_holdings = 1.0;
  input.required_holdings = 2.0;
  if (!expects(input, "insufficient_holdings")) return 1;
  input = ready;
  input.available_cash = 10.0;
  if (!expects(input, "insufficient_cash")) return 1;
  input = ready;
  input.live_execution_enabled = false;
  if (!expects(input, "live_execution_disabled")) return 1;

  std::cout << "execution preflight blocker and parity tests passed\n";
  return 0;
}
