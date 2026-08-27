#include "trading/LiveReconciliation.hpp"
#include "trading/PortfolioAccounting.hpp"

#include <iostream>
#include <string>

namespace {
bool expect(bool condition, const char *label) {
  if (!condition) {
    std::cerr << label << std::endl;
    return false;
  }
  return true;
}
}

int main() {
  using trade::trading::absolutePositionExposure;
  using trade::trading::coinbaseProductIdForAsset;
  using trade::trading::LivePendingOrderEvidence;
  using trade::trading::livePositionExposureVerified;
  using trade::trading::livePositionReconciliationStatus;
  using trade::trading::signedPositionValue;

  bool ok = true;
  ok &= expect(coinbaseProductIdForAsset("ETH") == "ETH-USD",
               "Coinbase asset normalization changed");
  ok &= expect(coinbaseProductIdForAsset("BTC") == "BTC-USD",
               "Coinbase symbol normalization changed");

  // A successful snapshot remains authoritative when a later refresh fails;
  // the failed refresh changes diagnostics, not the cached snapshot state.
  ok &= expect(livePositionExposureVerified(true, true, LivePendingOrderEvidence::none, false),
               "cached successful snapshot must verify a position");
  ok &= expect(std::string(livePositionReconciliationStatus(
                   true, true, LivePendingOrderEvidence::none, false)) ==
                   "coinbase_confirmed",
               "cached successful snapshot must remain confirmed after refresh failure");

  // No snapshot is fail-closed, including an absent position in an empty
  // snapshot. Only accepted pending orders and managed floors are bounded
  // recovery exceptions; submitting/ambiguous orders are not evidence.
  ok &= expect(!livePositionExposureVerified(
                   false, false, LivePendingOrderEvidence::none, false),
               "never-loaded snapshot must fail closed");
  ok &= expect(!livePositionExposureVerified(
                   true, false, LivePendingOrderEvidence::none, false),
               "absent ETH-USD must fail closed");
  ok &= expect(livePositionExposureVerified(
                   false, false, LivePendingOrderEvidence::accepted, false),
               "accepted pending order must preserve bounded recovery");
  ok &= expect(!livePositionExposureVerified(
                   false, false, LivePendingOrderEvidence::none, false),
               "submitting or ambiguous orders must remain fail-closed");
  ok &= expect(livePositionExposureVerified(
                   true, false, LivePendingOrderEvidence::none, true),
               "managed floor must preserve bounded recovery");
  ok &= expect(std::string(livePositionReconciliationStatus(
                       false, false, LivePendingOrderEvidence::accepted, false)) ==
                   "pending_settlement",
               "pending exception must be labeled");
  ok &= expect(std::string(livePositionReconciliationStatus(
                       true, false, LivePendingOrderEvidence::none, true)) ==
                   "awaiting_snapshot_reconciliation",
               "floor exception must be labeled");
  ok &= expect(std::string(livePositionReconciliationStatus(
                       true, false, LivePendingOrderEvidence::none, false)) ==
                   "stale_internal",
               "unverified position must be labeled");

  // Verified positions retain the existing signed-value/absolute-exposure
  // split used by portfolio totals and risk calculations.
  ok &= expect(signedPositionValue("buy", 2.0, 50.0) == 100.0,
               "verified long signed value changed");
  ok &= expect(absolutePositionExposure(2.0, 50.0) == 100.0,
               "verified absolute exposure changed");
  return ok ? 0 : 1;
}
