#include "trading/PortfolioAccounting.hpp"

#include <cmath>
#include <iostream>
#include <string>

using trade::trading::closeCashDelta;
using trade::trading::openCashDelta;
using trade::trading::absolutePositionExposure;
using trade::trading::signedPositionValue;

namespace {

bool expect_close(double actual, double expected, const char *label) {
  if (std::fabs(actual - expected) > 1e-9) {
    std::cerr << label << " expected " << expected << " got " << actual << std::endl;
    return false;
  }
  return true;
}

// Walks one open/mark/close cycle and asserts the identity
// total_value == cash + signed_positions_value at every step.
bool run_cycle(const std::string &side, double entry_price, double mark_price,
               double quantity, double fee_rate) {
  const double initial_capital = 10000.0;
  double cash = initial_capital;

  const double entry_notional = entry_price * quantity;
  const double open_fee = entry_notional * fee_rate;
  cash += openCashDelta(side, entry_notional, open_fee);

  // Immediately after open, before prices move, the position is worth its
  // entry notional and total value equals initial capital minus the fee.
  double positions_value = signedPositionValue(side, quantity, entry_price);
  if (!expect_close(cash + positions_value, initial_capital - open_fee,
                    (side + " open identity").c_str())) {
    return false;
  }

  // After a mark-to-market move, the identity gains exactly the unrealized PnL.
  positions_value = signedPositionValue(side, quantity, mark_price);
  const double direction = side == "buy" ? 1.0 : -1.0;
  const double unrealized = (mark_price - entry_price) * quantity * direction;
  if (!expect_close(cash + positions_value,
                    initial_capital - open_fee + unrealized,
                    (side + " marked identity").c_str())) {
    return false;
  }

  // Close at the marked price: value returns to cash and totals reconcile to
  // initial capital + realized PnL - all fees.
  const double exit_notional = mark_price * quantity;
  const double close_fee = exit_notional * fee_rate;
  cash += closeCashDelta(side, exit_notional, close_fee);
  if (!expect_close(cash, initial_capital + unrealized - open_fee - close_fee,
                    (side + " close identity").c_str())) {
    return false;
  }

  return true;
}

} // namespace

int main() {
  if (!run_cycle("buy", 100.0, 108.0, 5.0, 0.0005)) {
    return 1;
  }
  if (!run_cycle("buy", 100.0, 91.0, 5.0, 0.0005)) {
    return 1;
  }
  if (!run_cycle("sell", 100.0, 92.0, 5.0, 0.0005)) {
    return 1;
  }
  if (!run_cycle("sell", 100.0, 111.0, 5.0, 0.0005)) {
    return 1;
  }

  if (!expect_close(signedPositionValue("sell", 2.0, 50.0), -100.0,
                    "short signed value")) {
    return 1;
  }
  if (!expect_close(absolutePositionExposure(2.0, 50.0), 100.0,
                    "short absolute exposure")) {
    return 1;
  }
  if (!expect_close(1000.0 + signedPositionValue("sell", 2.0, 50.0), 900.0,
                    "cash plus short signed value identity")) {
    return 1;
  }

  // Percent sizing compounds with current total value; wiped equity falls
  // back to the provided capital.
  {
    using trade::trading::percentSizingCapital;
    if (!expect_close(percentSizingCapital(9000.0, 6000.0, 10000.0), 15000.0,
                      "sizing base = current value") ||
        !expect_close(percentSizingCapital(500.0, -300.0, 10000.0), 200.0,
                      "sizing base with net-short book") ||
        !expect_close(percentSizingCapital(-100.0, 50.0, 10000.0), 10000.0,
                      "wiped equity falls back to initial capital")) {
      return 1;
    }
  }

  // Cash-sufficiency gate: buys need notional + fee, shorts need collateral.
  {
    using trade::trading::hasSufficientCash;
    bool ok = true;
    ok &= hasSufficientCash("buy", 101.0, 100.0, 0.5);
    ok &= !hasSufficientCash("buy", 100.0, 100.0, 0.5);
    ok &= hasSufficientCash("sell", 100.0, 100.0, 0.5);
    ok &= !hasSufficientCash("sell", 99.0, 100.0, 0.5);
    if (!ok) {
      std::cerr << "cash sufficiency expectations failed" << std::endl;
      return 1;
    }
  }

  // Stop-loss / take-profit exit rule.
  {
    using trade::trading::exitReasonForPnl;
    bool ok = true;
    auto expect_reason = [&](const char *actual, const char *expected, const char *label) {
      const bool matches = (actual == nullptr && expected == nullptr) ||
                           (actual != nullptr && expected != nullptr &&
                            std::string(actual) == expected);
      if (!matches) {
        std::cerr << label << " expected " << (expected ? expected : "nullptr") << " got "
                  << (actual ? actual : "nullptr") << std::endl;
        ok = false;
      }
    };

    expect_reason(exitReasonForPnl(-2.1, 2.0, 3.0), "Stop loss triggered", "sl breach");
    expect_reason(exitReasonForPnl(3.5, 2.0, 3.0), "Take profit triggered", "tp breach");
    expect_reason(exitReasonForPnl(-1.9, 2.0, 3.0), nullptr, "inside band holds");
    expect_reason(exitReasonForPnl(-50.0, 0.0, 0.0), nullptr, "disabled thresholds hold");
    expect_reason(exitReasonForPnl(-2.0, 2.0, 0.0), "Stop loss triggered", "sl at threshold");
    expect_reason(exitReasonForPnl(3.0, 0.0, 3.0), "Take profit triggered", "tp at threshold");
    if (!ok) {
      return 1;
    }
  }

  // Pre-existing Coinbase holdings are visible but never strategy-liquidatable.
  {
    using trade::trading::managedSellQuantity;
    if (!expect_close(managedSellQuantity(10.0, 2.0, 10.0), 2.0,
                      "managed quantity caps sell") ||
        !expect_close(managedSellQuantity(10.0, 2.0, 1.25), 1.25,
                      "available quantity caps sell") ||
        !expect_close(managedSellQuantity(10.0, 0.0, 10.0), 0.0,
                      "unmanaged holding cannot be sold")) {
      return 1;
    }
  }
  return 0;
}
