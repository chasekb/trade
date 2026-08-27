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
  ok &= expect(livePositionExposureVerified(true, true, false, false),
               "cached successful snapshot must verify a position");
  ok &= expect(std::string(livePositionReconciliationStatus(true, true, false, false)) ==
                   "coinbase_confirmed",
               "cached successful snapshot must remain confirmed after refresh failure");

  // No snapshot is fail-closed, including an absent position in an empty
  // snapshot. Only the existing bounded pending/floor exceptions are kept.
  ok &= expect(!livePositionExposureVerified(false, false, false, false),
               "never-loaded snapshot must fail closed");
  ok &= expect(!livePositionExposureVerified(true, false, false, false),
               "absent ETH-USD must fail closed");
  ok &= expect(livePositionExposureVerified(false, false, true, false),
               "accepted pending order must preserve bounded recovery");
  ok &= expect(livePositionExposureVerified(true, false, false, true),
               "managed floor must preserve bounded recovery");
  ok &= expect(std::string(livePositionReconciliationStatus(false, false, true, false)) ==
                   "pending_settlement",
               "pending exception must be labeled");
  ok &= expect(std::string(livePositionReconciliationStatus(true, false, false, true)) ==
                   "awaiting_snapshot_reconciliation",
               "floor exception must be labeled");
  ok &= expect(std::string(livePositionReconciliationStatus(true, false, false, false)) ==
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