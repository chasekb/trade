#pragma once

#include <string>

namespace trade {
namespace trading {

// Pure cash-accounting helpers shared by the simulated trading engine and its
// tests. Convention: opening a long spends cash (notional + fee), opening a
// short credits the proceeds (notional - fee); closing reverses the leg. With
// this convention the identity
//   total_value == cash + signed_positions_value
// holds at every tick for both longs and shorts.

inline double openCashDelta(const std::string &side, double notional, double fee) {
  return side == "buy" ? -(notional + fee) : (notional - fee);
}

inline double closeCashDelta(const std::string &side, double exit_notional, double fee) {
  return side == "buy" ? (exit_notional - fee) : -(exit_notional + fee);
}

inline double signedPositionValue(const std::string &side, double quantity, double price) {
  const double market_value = quantity * price;
  return side == "buy" ? market_value : -market_value;
}

// Base capital for percent position sizing: percent of the *current* total
// value (cash + signed positions value) so sizing compounds with the session.
// Falls back to the given capital when equity is wiped or not yet established.
inline double percentSizingCapital(double cash, double signed_positions_value,
                                   double fallback_capital) {
  const double current_value = cash + signed_positions_value;
  return current_value > 0.0 ? current_value : fallback_capital;
}

// Cash-sufficiency gate for opening/adding to a position. Buys must cover the
// notional plus fee; shorts must hold the notional as free collateral (their
// fee comes out of the sale proceeds). Insufficient cash rejects the entry
// outright — no auto-scaling.
inline bool hasSufficientCash(const std::string &side, double cash, double allocated_usd,
                              double fee) {
  return side == "buy" ? cash >= allocated_usd + fee : cash >= allocated_usd;
}

// Stop-loss / take-profit exit rule over a position's PnL percentage. A zero
// or negative threshold disables that side. Returns the close reason, or
// nullptr when the position should stay open.
inline const char *exitReasonForPnl(double pnl_percentage, double stop_loss_percent,
                                    double take_profit_percent) {
  if (stop_loss_percent > 0.0 && pnl_percentage <= -stop_loss_percent) {
    return "Stop loss triggered";
  }
  if (take_profit_percent > 0.0 && pnl_percentage >= take_profit_percent) {
    return "Take profit triggered";
  }
  return nullptr;
}

} // namespace trading
} // namespace trade
