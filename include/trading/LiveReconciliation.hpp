#pragma once

#include <string>

namespace trade {
namespace trading {

inline std::string coinbaseProductIdForAsset(const std::string &asset) {
  return asset + "-USD";
}

enum class LivePendingOrderEvidence {
  none,
  accepted,
};

// A position is safe to include in live exposure only when the authoritative
// snapshot contains it, or an existing bounded recovery exception protects it.
inline bool livePositionExposureVerified(bool snapshot_loaded,
                                         bool snapshot_contains_position,
                                         LivePendingOrderEvidence pending_order_evidence,
                                         bool managed_floor_present) {
  return pending_order_evidence == LivePendingOrderEvidence::accepted ||
         managed_floor_present ||
         (snapshot_loaded && snapshot_contains_position);
}

// Compatibility adapter for existing callers; callers must pass only the
// result of the accepted-order predicate, never a submitting/ambiguous state.
inline bool livePositionExposureVerified(bool snapshot_loaded,
                                         bool snapshot_contains_position,
                                         bool accepted_pending_order_present,
                                         bool managed_floor_present) {
  return livePositionExposureVerified(
      snapshot_loaded, snapshot_contains_position,
      accepted_pending_order_present ? LivePendingOrderEvidence::accepted
                                     : LivePendingOrderEvidence::none,
      managed_floor_present);
}

inline const char *livePositionReconciliationStatus(
    bool snapshot_loaded, bool snapshot_contains_position,
    LivePendingOrderEvidence pending_order_evidence, bool managed_floor_present) {
  if (snapshot_loaded && snapshot_contains_position) {
    return "coinbase_confirmed";
  }
  if (pending_order_evidence == LivePendingOrderEvidence::accepted) {
    return "pending_settlement";
  }
  if (managed_floor_present) {
    return "awaiting_snapshot_reconciliation";
  }
  return "stale_internal";
}

inline const char *livePositionReconciliationStatus(
    bool snapshot_loaded, bool snapshot_contains_position,
    bool accepted_pending_order_present, bool managed_floor_present) {
  return livePositionReconciliationStatus(
      snapshot_loaded, snapshot_contains_position,
      accepted_pending_order_present ? LivePendingOrderEvidence::accepted
                                     : LivePendingOrderEvidence::none,
      managed_floor_present);
}

} // namespace trading
} // namespace trade
