#pragma once

#include <string>

namespace trade {
namespace trading {

inline std::string coinbaseProductIdForAsset(const std::string &asset) {
  return asset + "-USD";
}

// A position is safe to include in live exposure only when the authoritative
// snapshot contains it, or an existing bounded recovery exception protects it.
inline bool livePositionExposureVerified(bool snapshot_loaded,
                                         bool snapshot_contains_position,
                                         bool pending_order_present,
                                         bool managed_floor_present) {
  return pending_order_present || managed_floor_present ||
         (snapshot_loaded && snapshot_contains_position);
}

inline const char *livePositionReconciliationStatus(
    bool snapshot_loaded, bool snapshot_contains_position,
    bool pending_order_present, bool managed_floor_present) {
  if (snapshot_loaded && snapshot_contains_position) {
    return "coinbase_confirmed";
  }
  if (pending_order_present) {
    return "pending_settlement";
  }
  if (managed_floor_present) {
    return "awaiting_snapshot_reconciliation";
  }
  return "stale_internal";
}

} // namespace trading
} // namespace trade