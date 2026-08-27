#pragma once

#include <string>

namespace trade {
namespace trading {

struct LivePositionReconciliation {
  bool snapshot_loaded = false;
  bool snapshot_present = false;
  bool pending_order_present = false;
  bool managed_quantity_floor_present = false;
};

std::string livePositionReconciliationStatus(const LivePositionReconciliation &state);
bool livePositionContributesToExposure(const LivePositionReconciliation &state);

} // namespace trading
} // namespace trade
