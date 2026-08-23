#include "trading/ExecutionPreflight.hpp"

#include <algorithm>
#include <cmath>

namespace trade {
namespace trading {

ExecutionPreflightResult evaluate_execution_preflight(
    const ExecutionPreflightInputs &inputs) {
  ExecutionPreflightResult result;
  const auto blocked = [&result](const char *reason) {
    result.blocker_reason = reason;
    return result;
  };

  if (!inputs.account_ready) {
    return blocked("account_not_ready");
  }
  if (!inputs.account_entries_allowed) {
    return blocked("account_position_management_disabled");
  }
  if (!inputs.strategy_gate_passed) {
    result.blocker_reason = inputs.strategy_blocker_reason;
    return result;
  }
  if (inputs.existing_position) {
    return blocked("existing_position");
  }
  if (inputs.pending_order) {
    return blocked("pending_order");
  }
  if (inputs.max_positions == 0 ||
      inputs.managed_positions + inputs.pending_entries >= inputs.max_positions) {
    return blocked("max_positions");
  }
  if (!std::isfinite(inputs.allocated_usd) || !std::isfinite(inputs.price) ||
      inputs.allocated_usd <= 0.0 || inputs.price <= 0.0) {
    return blocked("nonpositive_position_size_or_price");
  }
  if (!std::isfinite(inputs.minimum_notional) ||
      inputs.allocated_usd < std::max(0.0, inputs.minimum_notional)) {
    return blocked("below_minimum_notional");
  }
  if (inputs.side != "buy" && inputs.side != "sell") {
    return blocked("spot_cannot_open_short");
  }
  if (inputs.side == "sell" &&
      (!std::isfinite(inputs.available_holdings) ||
       inputs.available_holdings + 1e-12 < inputs.required_holdings)) {
    return blocked("insufficient_holdings");
  }
  if (!std::isfinite(inputs.available_cash) || !std::isfinite(inputs.estimated_fee) ||
      inputs.available_cash + 1e-12 < inputs.allocated_usd + inputs.estimated_fee) {
    return blocked("insufficient_cash");
  }
  if (inputs.require_live_execution && !inputs.live_execution_enabled) {
    return blocked("live_execution_disabled");
  }

  result.executable = true;
  result.blocker_reason = "paper_fill";
  return result;
}

} // namespace trading
} // namespace trade
