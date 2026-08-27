#include "trading/LivePositionReconciliation.hpp"

#include <iostream>
#include <string>

namespace {

bool expect_status(const trade::trading::LivePositionReconciliation &state,
                   const std::string &expected_status, bool expected_exposure,
                   const char *label) {
  const std::string actual_status = trade::trading::livePositionReconciliationStatus(state);
  const bool actual_exposure = trade::trading::livePositionContributesToExposure(state);
  if (actual_status != expected_status || actual_exposure != expected_exposure) {
    std::cerr << label << " expected " << expected_status << "/"
              << (expected_exposure ? "included" : "excluded") << " got " << actual_status
              << "/" << (actual_exposure ? "included" : "excluded") << std::endl;
    return false;
  }
  return true;
}

} // namespace

int main() {
  using trade::trading::LivePositionReconciliation;
  bool ok = true;
  ok &= expect_status({false, false, false, false}, "unverified_no_snapshot", false,
                      "never-loaded position");
  ok &= expect_status({true, true, false, false}, "coinbase_confirmed", true,
                      "snapshot-confirmed position");
  ok &= expect_status({true, false, false, false}, "unverified_missing_from_snapshot", false,
                      "missing position");
  ok &= expect_status({true, false, true, false}, "pending_settlement", true,
                      "accepted pending order exception");
  ok &= expect_status({true, false, false, true}, "awaiting_snapshot_reconciliation", true,
                      "bounded fill floor exception");
  return ok ? 0 : 1;
}
