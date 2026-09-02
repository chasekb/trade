#include "trading/LivePositionReconciliation.hpp"

namespace trade {
namespace trading {

std::string livePositionReconciliationStatus(const LivePositionReconciliation &state) {
  if (state.snapshot_present) {
    return "coinbase_confirmed";
  }
  if (state.pending_order_present) {
    return "pending_settlement";
  }
  if (state.managed_quantity_floor_present) {
    return "awaiting_snapshot_reconciliation";
  }
  return state.snapshot_loaded ? "unverified_missing_from_snapshot"
                               : "unverified_no_snapshot";
}

bool livePositionContributesToExposure(const LivePositionReconciliation &state) {
  return state.snapshot_present || state.pending_order_present ||
         state.managed_quantity_floor_present;
}

} // namespace trading
} // namespace trade
